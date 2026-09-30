#!/usr/bin/env bash
# Deploy only the frontend. Application secrets and databases are never packaged.
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
server_alias="${1:-Agent-server}"
revision="$(git -C "$project_dir" rev-parse --short=12 HEAD)"
release="$(date -u +%Y%m%dT%H%M%SZ)-$revision"
package_dir="$(mktemp -d)"
trap 'rm -rf "$package_dir"' EXIT
cd "$project_dir/frontend"
VITE_API_BASE=/api npm run build
printf '%s\n' "$revision" > dist/revision.txt
tar -czf "$package_dir/frontend.tgz" -C dist .
ssh -o BatchMode=yes "$server_alias" "mkdir -p /home/ubuntu/cpo-release/frontend-releases/$release"
scp -q "$package_dir/frontend.tgz" "$server_alias:/home/ubuntu/cpo-release/frontend-releases/$release/frontend.tgz"
ssh -o BatchMode=yes "$server_alias" bash -s -- "$release" <<'REMOTE'
set -euo pipefail
release="$1"
staging="/home/ubuntu/cpo-release/frontend-releases/$release"
tar -xzf "$staging/frontend.tgz" -C "$staging"
rm "$staging/frontend.tgz"
sudo mkdir -p /var/www/cpo-releases
sudo cp -a "$staging" "/var/www/cpo-releases/$release"
sudo chmod -R a+rX "/var/www/cpo-releases/$release"
sudo ln -s "/var/www/cpo-releases/$release" "/var/www/cpo-console.next-$release"
if [ -d /var/www/cpo-console ] && [ ! -L /var/www/cpo-console ]; then
  sudo mv /var/www/cpo-console "/var/www/cpo-console.before-$release"
fi
sudo mv -Tf "/var/www/cpo-console.next-$release" /var/www/cpo-console
# Keep the initial release workspace consistent with the served frontend.
mkdir -p /home/ubuntu/cpo-release/amazon-ads-console/frontend/dist
cp -a "$staging/." /home/ubuntu/cpo-release/amazon-ads-console/frontend/dist/
printf 'Frontend release: %s\n' "$release"
REMOTE
