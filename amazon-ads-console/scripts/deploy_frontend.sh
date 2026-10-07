#!/usr/bin/env bash
# Compatibility entry: releases now include frontend AND backend from a Git commit.
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
if [ "$#" -lt 2 ]; then
  printf 'Usage: %s prepare|deploy|rollback TAG_OR_COMMIT [--server Agent-server]\n' "$0" >&2
  exit 2
fi
exec python3 "$script_dir/release.py" "$@"
