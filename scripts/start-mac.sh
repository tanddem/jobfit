#!/usr/bin/env bash
# Build the JobFit image and run it on http://localhost:8000.
set -euo pipefail
cd "$(dirname "$0")/.."

docker build -t jobfit .
docker rm -f jobfit >/dev/null 2>&1 || true

env_args=()
if [ -f .env ]; then env_args=(--env-file .env); fi

docker run -d --name jobfit -p 8000:8000 -v jobfit-data:/data "${env_args[@]+"${env_args[@]}"}" jobfit >/dev/null
echo "JobFit is running at http://localhost:8000"
