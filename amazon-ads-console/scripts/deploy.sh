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
# Check under the same deployment lock used by activation, so concurrent tasks
# cannot publish over a newer release after their preparation completed.
if [ "$mode" != --prepare-only ]; then
  python3 - "$approval" "$base/current/release.json" <<'PY'
import json,sys
approval=json.load(open(sys.argv[1]))
expected=approval.get('expected_current_commit')
if expected:
 current=json.load(open(sys.argv[2]))['commit']
 if current != expected:
  raise SystemExit('Production changed during preparation; integrate the current release before activating.')
PY
fi
[ "$(git --git-dir="$repo" rev-parse "$commit^{commit}")" = "$commit" ]
# The orchestrator may be newer than an application rollback target. Verify both
# helper files against its approved Git commit before any preparation/activation.
engine_commit="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["engine_commit"])' "$approval")"
python3 - "$repo" "$engine_commit" "$script_dir" <<'PY'
import subprocess,sys
from pathlib import Path
repo,commit,directory=sys.argv[1:]
for filename,path in [('deploy.sh','scripts/deploy.sh'),('cache_release.py','deploy/cache_release.py'),('rolling_release.py','deploy/rolling_release.py')]:
 expected=subprocess.check_output(['git','--git-dir='+repo,'show',commit+':amazon-ads-console/'+path])
 assert (Path(directory)/filename).read_bytes()==expected, 'Deployment engine differs from approved Git commit'
PY
release="$base/releases/$commit"
staging="$base/releases/.staging-$commit-$$"
audit_id="$(date -u +%Y%m%dT%H%M%SZ)-$commit"

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
cleanup() {
  result="$?"
  set +e
  trap - EXIT
  [ ! -d "$staging" ] || rm -rf "$staging"
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
# Read the helper from the verified engine so application rollbacks to versions
# without this helper retain compatible assets too. Preparation is additive.
git --git-dir="$repo" show "$engine_commit":amazon-ads-console/deploy/retain_frontend_assets.py | python3 - "$base/releases" "$release"
(
  cd "$release/amazon-ads-console/backend"
  "$release/.venv/bin/python" ../deploy/health_check.py "$release"
)
if [ "$mode" = --prepare-only ]; then
  write_event PREPARED
  printf 'Prepared Git release %s; production remains unchanged.\n' "$commit"
  exit 0
fi

# Candidate startup, prewarming, traffic switch and rollback are owned by the
# verified rolling engine. It never clears snapshots used by a live worker.
write_event ACTIVATING
if ! sudo -n /usr/bin/python3 "$script_dir/rolling_release.py" activate "$release"; then
  write_event FAILED_ROLLING_ACTIVATION
  exit 7
fi
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
printf 'Published Git release %s; health OK.\n' "$commit"
