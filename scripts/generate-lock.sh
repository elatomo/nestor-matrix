#!/usr/bin/env bash
# Generate uv.lock using Docker with Python 3.14
#
# This ensures the lock file is generated in an environment where python-olm can
# be built successfully (Debian's older CMake accepts the bundled libolm's
# CMakeLists.txt).

set -euo pipefail

readonly LOCK_IMAGE="nestor-lock"

echo "🐳 Building lock generator image..."
docker build -t "$LOCK_IMAGE" -f Dockerfile.lock . -q

echo "🔒 Generating uv.lock..."
docker run --rm -v "$(pwd):/workspace" "$LOCK_IMAGE"

# Fix ownership (Docker creates files as root)
if [ "$(uname)" = "Linux" ]; then
    sudo chown "$(id -u):$(id -g)" uv.lock
fi

echo "✅ Lock file generated successfully"
echo ""
echo "Next steps:"
echo "  1. Verify: git diff uv.lock pyproject.toml"
echo "  2. Commit: git add uv.lock pyproject.toml && git commit -m 'Update lock file'"
echo ""
