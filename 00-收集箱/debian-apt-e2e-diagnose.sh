#!/usr/bin/env bash
set -u

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  exec sudo bash "$0" "$@"
fi

export DEBIAN_FRONTEND=noninteractive

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="${SUDO_USER:+/home/$SUDO_USER}/apt-diagnose-$STAMP"
if [ -z "${SUDO_USER:-}" ] || [ ! -d "${SUDO_USER:+/home/$SUDO_USER}" ]; then
  OUT_DIR="$PWD/apt-diagnose-$STAMP"
fi
mkdir -p "$OUT_DIR"
LOG="$OUT_DIR/report.log"

run() {
  printf '\n\n===== %s =====\n' "$*"
  "$@"
}

run_allow_fail() {
  printf '\n\n===== %s =====\n' "$*"
  "$@" || printf 'COMMAND_EXITED_WITH_STATUS=%s\n' "$?"
}

{
  printf 'APT diagnose started: %s\n' "$(date -Is)"
  printf 'Arguments: %s\n' "$*"

  run_allow_fail cat /etc/os-release
  run_allow_fail uname -a
  run_allow_fail dpkg --print-architecture
  run_allow_fail dpkg --print-foreign-architectures
  run_allow_fail df -h /
  run_allow_fail timedatectl

  printf '\n\n===== apt source files =====\n'
  find /etc/apt -maxdepth 3 \( -name '*.list' -o -name '*.sources' \) -print -exec sed -n '1,220p' {} \;

  run_allow_fail apt-mark showhold
  run_allow_fail dpkg --audit
  run_allow_fail apt-get check

  printf '\n\n===== package locks =====\n'
  for lock in /var/lib/dpkg/lock /var/lib/dpkg/lock-frontend /var/cache/apt/archives/lock /var/lib/apt/lists/lock; do
    [ -e "$lock" ] && run_allow_fail fuser -v "$lock"
  done

  run_allow_fail apt-get update
  run_allow_fail apt-cache policy
  run_allow_fail apt-get -s -f install

  if [ "$#" -gt 0 ]; then
    for target in "$@"; do
      printf '\n\n===== target: %s =====\n' "$target"
      if [ -f "$target" ]; then
        run_allow_fail dpkg-deb -I "$target"
        run_allow_fail apt-get -s install "$target"
      else
        run_allow_fail apt-cache policy "$target"
        run_allow_fail apt-get -s install "$target"
      fi
    done
  else
    printf '\n\n===== no target package supplied =====\n'
    printf 'Re-run with a package name or .deb path, for example:\n'
    printf '  sudo bash debian-apt-e2e-diagnose.sh google-chrome-stable\n'
    printf '  sudo bash debian-apt-e2e-diagnose.sh ./some-package.deb\n'
  fi

  printf '\n\n===== recent apt and dpkg logs =====\n'
  for f in /var/log/apt/history.log /var/log/apt/term.log /var/log/dpkg.log; do
    [ -f "$f" ] && { printf '\n--- %s ---\n' "$f"; tail -n 220 "$f"; }
  done

  printf '\nAPT diagnose finished: %s\n' "$(date -Is)"
} 2>&1 | tee "$LOG"

tar -czf "$OUT_DIR.tar.gz" -C "$(dirname "$OUT_DIR")" "$(basename "$OUT_DIR")"
printf '\nCreated diagnostic bundle:\n%s.tar.gz\n' "$OUT_DIR"
