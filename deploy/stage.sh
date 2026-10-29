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
# $HOME may be a network drive (H:); %USERPROFILE% is the real profile dir.
OLLAMA_MODELS_SRC="${OLLAMA_MODELS_SRC:-$(cygpath -u "$USERPROFILE" 2>/dev/null || echo "$HOME")/.ollama/models}"
STAGE="${STAGE_DIR:-stage-out}"
# Dev machine egress goes through the local Cntlm proxy.
export HTTPS_PROXY="${HTTPS_PROXY:-http://localhost:63328}"
export HTTP_PROXY="${HTTP_PROXY:-http://localhost:63328}"

rm -rf "$STAGE"
mkdir -p "$STAGE/wheels" "$STAGE/models"

echo "==> frontend build"
(cd frontend && "$NPM" ci && "$NPM" run build)
tar -czf "$STAGE/dist.tar.gz" -C frontend dist

echo "==> Linux wheels (cp311 / manylinux2014+2_28_x86_64)"
"$PY" -m pip download -r backend/requirements.lock -d "$STAGE/wheels" \
  --platform manylinux2014_x86_64 --platform manylinux_2_28_x86_64 \
  --python-version 3.11 --implementation cp --abi cp311 --only-binary=:all:
# uvloop is unix-only -> absent from a Windows-frozen lock, but
# uvicorn[standard] requires it on Linux. Fetch it explicitly.
"$PY" -m pip download uvloop -d "$STAGE/wheels" \
  --platform manylinux2014_x86_64 --platform manylinux_2_28_x86_64 \
  --python-version 3.11 --implementation cp --abi cp311 --only-binary=:all:
# pysqlite3-binary provides sqlite>=3.35 for Chroma on RHEL 8 (system: 3.26).
"$PY" -m pip download pysqlite3-binary -d "$STAGE/wheels" \
  --platform manylinux2014_x86_64 --platform manylinux_2_28_x86_64 \
  --python-version 3.11 --implementation cp --abi cp311 --only-binary=:all:

echo "==> Ollama binary (GitHub release asset, zst -> tgz recompress)"
# Releases ship .tar.zst; Alma 8 tar has no zstd rootless — recompress here.
curl -fsSL -o "$STAGE/ollama-linux-amd64.tar.zst" \
  https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64.tar.zst
"$PY" - "$STAGE" <<'PYEOF'
import gzip, shutil, sys, os
import zstandard as zstd
stage = sys.argv[1]
src = os.path.join(stage, "ollama-linux-amd64.tar.zst")
dst = os.path.join(stage, "ollama-linux-amd64.tgz")
with open(src, "rb") as fi, open(dst, "wb") as fo:
    with zstd.ZstdDecompressor().stream_reader(fi) as reader, \
         gzip.GzipFile(fileobj=fo, mode="wb", compresslevel=6) as gz:
        shutil.copyfileobj(reader, gz)
os.remove(src)
print(f"recompressed -> {dst}")
PYEOF

echo "==> Ollama models from $OLLAMA_MODELS_SRC"
cp -r "$OLLAMA_MODELS_SRC/." "$STAGE/models/"

echo "==> bundling"
tar -czf documind-stage.tar.gz -C "$STAGE" .
du -sh documind-stage.tar.gz
echo "Done. Next:"
echo "  scp documind-stage.tar.gz documind@ls-dp-integration-test:~/"
echo "  ssh documind@ls-dp-integration-test 'mkdir -p ~/documind-stage && tar -xzf ~/documind-stage.tar.gz -C ~/documind-stage'"
