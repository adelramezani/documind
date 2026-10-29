#!/usr/bin/env bash
# Build the offline deploy bundle on the dev machine (Git Bash).
#
# Produces documind-stage.tar.gz containing:
#   dist.tar.gz              prebuilt frontend (npm ci + npm run build)
#   wheels/                  Linux cp311 wheels for backend/requirements.lock
#   ollama-linux-amd64.tgz   Ollama server binary
#   models/                  Ollama model store (manifests + blobs)
#
# Usage:
#   ./deploy/stage.sh                       # build the bundle
#   scp documind-stage.tar.gz documind@ls-dp-integration-test:~/
#   # on the server:
#   mkdir -p ~/documind-stage && tar -xzf ~/documind-stage.tar.gz -C ~/documind-stage
set -euo pipefail
cd "$(dirname "$0")/.."

NPM="${NPM:-/c/Development/nodejs24/npm.cmd}"   # bare `npm` is a broken shim here
PY="${PY:-.venv/Scripts/python}"
OLLAMA_MODELS_SRC="${OLLAMA_MODELS_SRC:-$HOME/.ollama/models}"
STAGE="${STAGE_DIR:-stage-out}"

rm -rf "$STAGE"
mkdir -p "$STAGE/wheels" "$STAGE/models"

echo "==> frontend build"
(cd frontend && "$NPM" ci && "$NPM" run build)
tar -czf "$STAGE/dist.tar.gz" -C frontend dist

echo "==> Linux wheels (cp311 / manylinux2014_x86_64)"
"$PY" -m pip download -r backend/requirements.lock -d "$STAGE/wheels" \
  --platform manylinux2014_x86_64 --python-version 3.11 \
  --implementation cp --abi cp311 --only-binary=:all:

echo "==> Ollama binary (GitHub release asset)"
curl -fsSL -o "$STAGE/ollama-linux-amd64.tgz" \
  https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64.tgz

echo "==> Ollama models from $OLLAMA_MODELS_SRC"
cp -r "$OLLAMA_MODELS_SRC/." "$STAGE/models/"

echo "==> bundling"
tar -czf documind-stage.tar.gz -C "$STAGE" .
du -sh documind-stage.tar.gz
echo "Done. Next:"
echo "  scp documind-stage.tar.gz documind@ls-dp-integration-test:~/"
echo "  ssh documind@ls-dp-integration-test 'mkdir -p ~/documind-stage && tar -xzf ~/documind-stage.tar.gz -C ~/documind-stage'"
