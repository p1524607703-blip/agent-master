#!/usr/bin/env bash
# Server-side release engine. Code always comes from a verified Git object database.
set -euo pipefail
base=/opt/agent/cpo
repo="$base/repository.git"
commit="${1:-}"
mode="${2:-}"
if [[ ! "$commit" =~ ^[0-9a-f]{40}$ ]] || [[ "$mode" != '' && "$mode" != --prepare-only ]]; then
  printf 'Usage: deploy.sh FULL_COMMIT [--prepare-only]\n' >&2
  exit 2
fi
exec 9>"$base/deploy.lock"
flock -n 9 || { printf 'Another release is in progress.\n' >&2; exit 3; }
approval="$base/shared/approvals/$commit.json"
[ -f "$approval" ] || { printf 'Commit has not been verified against GitHub.\n' >&2; exit 4; }
python3 - "$approval" "$commit" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))['commit'] == sys.argv[2]
PY
[ "$(git --git-dir="$repo" rev-parse "$commit^{commit}")" = "$commit" ]
release="$base/releases/$commit"
staging="$base/releases/.staging-$commit-$$"
activating=0
old_current=''
old_front=''
audit_id="$(date -u +%Y%m%dT%H%M%SZ)-$commit"
unit_backup="$base/shared/unit-before-$audit_id.service"

write_event() {
  python3 - "$base" "$commit" "$1" "$approval" "$audit_id" <<'PY'
import json,sys
from pathlib import Path
from datetime import datetime,timezone
base,commit,status,approval,event_id=sys.argv[1:]
a=json.load(open(approval))
d={**a,'status':status,'event_id':event_id,'time':datetime.now(timezone.utc).isoformat(),'database_changes':False}
p=Path(base)/'shared/events.jsonl'
with p.open('a') as f:f.write(json.dumps(d)+'\n')
p.chmod(0o600)
if status=='OK':
 p=Path(base)/'shared/current-release.json';p.write_text(json.dumps(d,indent=2));p.chmod(0o600)
PY
}
cleanup() {
  result="$?"
  trap - EXIT
  [ ! -d "$staging" ] || rm -rf "$staging"
  if [ "$result" -ne 0 ] && [ "$activating" = 1 ]; then
    printf 'Release failed; restoring previous code and service.\n' >&2
    if [ -n "$old_current" ]; then
      ln -s "$old_current" "$base/current.rollback-$audit_id"
      mv -Tf "$base/current.rollback-$audit_id" "$base/current"
    else
      rm -f "$base/current"
    fi
    if [ -n "$old_front" ]; then
      sudo ln -s "$old_front" "/var/www/cpo-console.rollback-$audit_id"
      sudo mv -Tf "/var/www/cpo-console.rollback-$audit_id" /var/www/cpo-console
    fi
    sudo cp "$unit_backup" /etc/systemd/system/cpo-console.service
    sudo systemctl daemon-reload
    sudo systemctl restart cpo-console
    if sudo systemctl is-active --quiet cpo-console; then
      write_event FAILED_ROLLED_BACK
    else
      write_event FAILED_ROLLBACK_UNHEALTHY
      printf 'Previous service could not be restarted; inspect cpo-console logs.\n' >&2
    fi
  fi
  exit "$result"
}
trap cleanup EXIT

if [ ! -f "$release/release.json" ]; then
  mkdir -p "$staging"
  mkdir -p "$staging/amazon-ads-console" "$staging/ad-reports-export"
  # Archive the CPO subtree: Git must not hydrate unrelated vault files.
  GIT_NO_LAZY_FETCH=1 git --git-dir="$repo" archive "$commit:amazon-ads-console" | tar -xf - -C "$staging/amazon-ads-console"
  GIT_NO_LAZY_FETCH=1 git --git-dir="$repo" show "$commit:database_config.py" > "$staging/database_config.py"
  GIT_NO_LAZY_FETCH=1 git --git-dir="$repo" show "$commit:ad-reports-export/subscribed_reports_to_rds.py" > "$staging/ad-reports-export/subscribed_reports_to_rds.py"
  ln -s "$base/shared/backend.env" "$staging/amazon-ads-console/backend/.env"
  ln -s "$base/shared/uploads" "$staging/amazon-ads-console/backend/.cpo_uploads"
  if ! command -v node >/dev/null || ! command -v npm >/dev/null; then
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nodejs npm
  fi
  uv="$HOME/.local/bin/uv"
  [ -x "$uv" ] || { printf 'Install the Python uv runtime before preparing a release.\n' >&2; exit 5; }
  "$uv" venv --python 3.12 "$staging/.venv"
  "$uv" pip install --python "$staging/.venv/bin/python" -r "$staging/amazon-ads-console/backend/requirements.lock.txt"
  (
    cd "$staging/amazon-ads-console/frontend"
    npm ci --no-audit --no-fund --fetch-retries=1 --fetch-timeout=30000
    VITE_API_BASE=/api npm run build
  )
  python3 - "$staging" "$approval" "$commit" <<'PY'
import json,sys
from pathlib import Path
from datetime import datetime,timezone
root,approval,commit=sys.argv[1:];root=Path(root)
a=json.load(open(approval))
d={**a,'commit':commit,'prepared_at':datetime.now(timezone.utc).isoformat(),'health':'PREPARED','database_changes':False}
(root/'release.json').write_text(json.dumps(d,indent=2))
(root/'amazon-ads-console/frontend/dist/version.json').write_text(json.dumps(d))
(root/'amazon-ads-console/frontend/dist/revision.txt').write_text(commit[:12]+'\n')
PY
  mv "$staging" "$release"
fi
# These checks run again even for a previously prepared release.
git --git-dir="$repo" show "$commit":amazon-ads-console/deploy/verify_release.py | python3 - "$repo" "$release" "$commit"
(
  cd "$release/amazon-ads-console/backend"
  "$release/.venv/bin/python" ../deploy/health_check.py "$release"
)
if [ "$mode" = --prepare-only ]; then
  write_event PREPARED
  printf 'Prepared Git release %s; production remains unchanged.\n' "$commit"
  exit 0
fi

# Activation is an explicit action; no push hook or timer calls this section.
old_current="$(readlink "$base/current" || true)"
old_front="$(readlink /var/www/cpo-console || true)"
[ -n "$old_front" ] || { printf 'The frontend root must be a symlink before activation.\n' >&2; exit 6; }
sudo cat /etc/systemd/system/cpo-console.service > "$unit_backup"
chmod 600 "$unit_backup"
write_event ACTIVATING
activating=1
if [ -z "$old_current" ] && [ -d /home/ubuntu/cpo-release/amazon-ads-console/backend/.cpo_uploads ]; then
  # First switch: finish in-flight uploads before the final shared-file copy.
  sudo systemctl stop cpo-console
  cp -a /home/ubuntu/cpo-release/amazon-ads-console/backend/.cpo_uploads/. "$base/shared/uploads/"
fi
ln -s "$release" "$base/current.next-$audit_id"
mv -Tf "$base/current.next-$audit_id" "$base/current"
sudo ln -s "$base/current/amazon-ads-console/frontend/dist" "/var/www/cpo-console.next-$audit_id"
sudo mv -Tf "/var/www/cpo-console.next-$audit_id" /var/www/cpo-console
sudo cp "$release/amazon-ads-console/deploy/cpo-console.service" /etc/systemd/system/cpo-console.service
sudo systemctl daemon-reload
sudo systemctl restart cpo-console
public_url="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["public_url"])' "$approval")"
healthy=0
for attempt in $(seq 1 12); do
  if sudo systemctl is-active --quiet cpo-console && (
    cd "$release/amazon-ads-console/backend"
    "$release/.venv/bin/python" ../deploy/health_check.py "$release" --public-url "$public_url"
  ); then
    healthy=1
    break
  fi
  sleep 2
done
[ "$healthy" = 1 ] || { printf 'Release health checks failed.\n' >&2; exit 7; }
python3 - "$release" <<'PY'
import json,sys
from pathlib import Path
from datetime import datetime,timezone
root=Path(sys.argv[1]);p=root/'release.json';d=json.loads(p.read_text())
d.update(health='OK',deployed_at=datetime.now(timezone.utc).isoformat())
p.write_text(json.dumps(d,indent=2));(root/'amazon-ads-console/frontend/dist/version.json').write_text(json.dumps(d))
PY
write_event OK
activating=0
printf 'Published Git release %s; health OK.\n' "$commit"
