#!/usr/bin/env bash
# Server-side release engine. Code always comes from a verified Git object database.
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
base=/opt/agent/cpo
repo="$base/repository.git"
commit="${1:-}"
mode="${2:-}"
if [[ ! "$commit" =~ ^[0-9a-f]{40}$ ]] || [[ "$mode" != '' && "$mode" != --prepare-only && "$mode" != --rollback ]]; then
  printf 'Usage: deploy.sh FULL_COMMIT [--prepare-only|--rollback]\n' >&2
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
# The orchestrator may be newer than an application rollback target. Verify both
# helper files against its approved Git commit before any preparation/activation.
engine_commit="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["engine_commit"])' "$approval")"
python3 - "$repo" "$engine_commit" "$script_dir" <<'PY'
import subprocess,sys
from pathlib import Path
repo,commit,directory=sys.argv[1:]
for filename,path in [('deploy.sh','scripts/deploy.sh'),('cache_release.py','deploy/cache_release.py')]:
 expected=subprocess.check_output(['git','--git-dir='+repo,'show',commit+':amazon-ads-console/'+path])
 assert (Path(directory)/filename).read_bytes()==expected, 'Deployment engine differs from approved Git commit'
PY
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
if status in {'OK','ROLLED_BACK'}:
 p=Path(base)/'shared/current-release.json';p.write_text(json.dumps(d,indent=2));p.chmod(0o600)
PY
}
cache_action() {
  target_release="$1"
  (
    cd "$target_release/amazon-ads-console/backend"
    # The new, Git-verified helper also supports a previous release's backend.
    timeout 240 "$target_release/.venv/bin/python" "$script_dir/cache_release.py" "$target_release" "$2"
  )
}
wait_ready() {
  for attempt in $(seq 1 60); do
    if sudo -n systemctl is-active --quiet cpo-console && python3 - <<'PY'
import urllib.request,urllib.error
try:
 urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:8000/api/auth/me',timeout=3)
except urllib.error.HTTPError as error:
 raise SystemExit(0 if error.code==401 else 1)
except Exception:
 raise SystemExit(1)
raise SystemExit(1)
PY
    then return 0; fi
    sleep 2
  done
  return 1
}
release_health() {
  target_release="$1"
  target_url="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["public_url"])' "$target_release/release.json")"
  (
    cd "$target_release/amazon-ads-console/backend"
    "$target_release/.venv/bin/python" ../deploy/health_check.py "$target_release" --public-url "$target_url"
  )
}
cleanup() {
  result="$?"
  set +e
  trap - EXIT
  [ ! -d "$staging" ] || rm -rf "$staging"
  if [ "$result" -ne 0 ] && [ "$activating" = 1 ]; then
    printf 'Release failed; restoring previous code and service.\n' >&2
    # Stop the candidate before deleting snapshots: active loaders must never
    # repopulate the cache with an implementation which is about to be replaced.
    sudo -n systemctl stop cpo-console || true
    rollback_ok=1
    cache_action "$release" clear || rollback_ok=0
    if [ -n "$old_current" ]; then
      ln -s "$old_current" "$base/current.rollback-$audit_id"
      mv -Tf "$base/current.rollback-$audit_id" "$base/current"
    else
      rm -f "$base/current"
    fi
    if [ -n "$old_front" ]; then
      sudo -n ln -s "$old_front" "/var/www/cpo-console.rollback-$audit_id"
      sudo -n mv -Tf "/var/www/cpo-console.rollback-$audit_id" /var/www/cpo-console
    fi
    sudo -n cp "$unit_backup" /etc/systemd/system/cpo-console.service
    sudo -n systemctl daemon-reload
    sudo -n systemctl restart cpo-console || rollback_ok=0
    if [ -n "$old_current" ]; then
      wait_ready || rollback_ok=0
      cache_action "$old_current" prewarm || rollback_ok=0
      release_health "$old_current" || rollback_ok=0
    else
      rollback_ok=0
    fi
    if [ "$rollback_ok" = 1 ]; then
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
  mkdir -p "$staging/amazon-ads-console"
  # Archive only the CPO subtree: Git must not hydrate unrelated repository files.
  GIT_NO_LAZY_FETCH=1 git --git-dir="$repo" archive "$commit:amazon-ads-console" | tar -xf - -C "$staging/amazon-ads-console"
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
sudo -n cat /etc/systemd/system/cpo-console.service > "$unit_backup"
chmod 600 "$unit_backup"
write_event ACTIVATING
activating=1
# Every activation and explicit rollback follows the same race-free sequence.
sudo -n systemctl stop cpo-console
cache_action "$release" clear
if [ -z "$old_current" ] && [ -d /home/ubuntu/cpo-release/amazon-ads-console/backend/.cpo_uploads ]; then
  # First switch: finish in-flight uploads before the final shared-file copy.
  cp -a /home/ubuntu/cpo-release/amazon-ads-console/backend/.cpo_uploads/. "$base/shared/uploads/"
fi
ln -s "$release" "$base/current.next-$audit_id"
mv -Tf "$base/current.next-$audit_id" "$base/current"
sudo -n ln -s "$base/current/amazon-ads-console/frontend/dist" "/var/www/cpo-console.next-$audit_id"
sudo -n mv -Tf "/var/www/cpo-console.next-$audit_id" /var/www/cpo-console
sudo -n cp "$release/amazon-ads-console/deploy/cpo-console.service" /etc/systemd/system/cpo-console.service
sudo -n systemctl daemon-reload
sudo -n systemctl restart cpo-console
wait_ready || { printf 'Release readiness check failed.\n' >&2; exit 7; }
cache_action "$release" prewarm
release_health "$release" || { printf 'Release health checks failed.\n' >&2; exit 7; }
python3 - "$release" "$approval" <<'PY'
import json,sys
from pathlib import Path
from datetime import datetime,timezone
root=Path(sys.argv[1]);p=root/'release.json';d=json.loads(p.read_text())
d.update(json.load(open(sys.argv[2])))
d.update(health='OK',deployed_at=datetime.now(timezone.utc).isoformat())
p.write_text(json.dumps(d,indent=2));(root/'amazon-ads-console/frontend/dist/version.json').write_text(json.dumps(d))
PY
if [ "$mode" = --rollback ]; then
  write_event ROLLED_BACK
else
  write_event OK
fi
activating=0
printf 'Published Git release %s; health OK.\n' "$commit"
