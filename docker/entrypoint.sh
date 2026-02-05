#!/usr/bin/env bash
set -euo pipefail

workspaceDir="/home/simulation/dbn-sim-learning"
sharedDirs=("plots" "results" "traces")

# Normalize how commands are passed:
# - default: interactive bash
# - allow: docker run <img> -lc 'cmd'
# - allow: docker run <img> bash -lc 'cmd'
if [ "$#" -eq 0 ]; then
  set -- /bin/bash
elif [ "${1:-}" = "bash" ]; then
  shift
  set -- /bin/bash "$@"
elif [[ "${1:-}" = -* ]]; then
  set -- /bin/bash "$@"
fi

# If running as root, fix ownership of bind-mounted dirs (best-effort) then drop privileges.
if [ "$(id -u)" -eq 0 ]; then
  for d in "${sharedDirs[@]}"; do
    mkdir -p "$workspaceDir/$d"
    chown -R simulation:simulation "$workspaceDir/$d" 2>/dev/null || true
  done

  exec runuser -u simulation -- "$@"
fi

exec "$@"
