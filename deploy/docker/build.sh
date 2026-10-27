#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_dir/argilla-frontend"
npm ci --no-audit --no-fund
node node_modules/nuxt/bin/nuxt.js generate --config-file nuxt.deploy.config.ts
cd "$repo_dir"
docker build --build-arg "VCS_REF=$(git rev-parse HEAD)" -t "${ARGILLA_IMAGE:-argilla-local:develop}" .
