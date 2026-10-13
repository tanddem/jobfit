#!/usr/bin/env bash
# Stop and remove the JobFit container. The jobfit-data volume is kept.
set -euo pipefail

if [ -n "$(docker ps -aq --filter name=^jobfit$)" ]; then
  docker rm -f jobfit >/dev/null
  echo "JobFit stopped."
else
  echo "JobFit was not running."
fi
