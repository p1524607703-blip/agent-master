#!/usr/bin/env bash
set -euo pipefail

HOOK="/etc/dpkg/dpkg.cfg.d/10deb-verifysign"
DISABLED="/etc/dpkg/dpkg.cfg.d/10deb-verifysign.disabled"

usage() {
  cat <<'USAGE'
Usage:
  uos-install-unsigned-deb /path/to/package.deb

Installs a trusted third-party .deb on UOS by temporarily disabling the
deepin deb signature verification hook, then restoring it automatically.
USAGE
}

if [ "$#" -ne 1 ] || [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 1
fi

PKG="$1"
if [ ! -f "$PKG" ]; then
  echo "Package not found: $PKG" >&2
  exit 1
fi

if [ "${PKG##*.}" != "deb" ]; then
  echo "Refusing to install non-.deb file: $PKG" >&2
  exit 1
fi

restore_hook() {
  if [ -e "$DISABLED" ] && [ ! -e "$HOOK" ]; then
    sudo mv "$DISABLED" "$HOOK"
    echo "Restored UOS deb verification hook."
  fi
}

trap restore_hook EXIT INT TERM

echo "Preparing to install trusted third-party package:"
echo "  $PKG"
echo
echo "The UOS deb verification hook will be disabled only during this install."
sudo -v

if [ -e "$DISABLED" ] && [ ! -e "$HOOK" ]; then
  echo "Verification hook is already disabled; continuing and will restore it after install."
elif [ -e "$HOOK" ]; then
  sudo mv "$HOOK" "$DISABLED"
  echo "Temporarily disabled UOS deb verification hook."
else
  echo "Warning: verification hook not found at $HOOK" >&2
fi

sudo apt install "$PKG"
restore_hook

echo
echo "Running package database check..."
sudo apt-get check
echo "Done."
