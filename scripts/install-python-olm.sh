#!/usr/bin/env bash
# Build and install python-olm from source with CMake compatibility patch
#
# Why this is needed:
# - python-olm bundled CMakeLists.txt requires CMake 3.4
# - CMake 4.x removed support for declaring minimum versions < 3.5
# - This patches the requirement to 3.5 (minimum supported by CMake 4.x)
#
# When to use:
# - Python 3.14+ (no precompiled wheels available)
# - CMake 4.x installed (rejects CMake 3.4 requirement)
# - After `uv sync` fails to install python-olm

set -euo pipefail

readonly PYTHON_OLM_VERSION="3.2.16"
readonly PYTHON_OLM_TARBALL="python-olm-${PYTHON_OLM_VERSION}.tar.gz"
readonly PYTHON_OLM_DIR="python-olm-${PYTHON_OLM_VERSION}"

main() {
    # Verify we're in a uv project with virtualenv
    if [[ ! -d .venv ]]; then
        echo "❌ Error: No .venv found in current directory" >&2
        echo "   Run this script from the project root after 'uv sync'" >&2
        exit 1
    fi

    # Check if already installed
    if uv run python -c "import olm" 2>/dev/null; then
        echo "✅ python-olm is already installed"
        exit 0
    fi

    echo "🔍 Building python-olm from source"
    echo "   Python: $(python --version)"
    echo "   Architecture: $(uname -m)"
    echo ""

    install_build_deps
    build_from_source

    echo "✅ Successfully installed python-olm"
}

install_build_deps() {
    if command -v pacman >/dev/null 2>&1; then
        echo "📦 Installing dependencies (Arch Linux)..."
        sudo pacman -S --needed --noconfirm libolm cmake
    elif command -v apt-get >/dev/null 2>&1; then
        echo "📦 Installing dependencies (Debian/Ubuntu)..."
        # TODO: Verify dependencies!
        sudo apt-get update
        sudo apt-get install -y libolm-dev cmake build-essential python3-dev libffi-dev
    else
        echo "❌ Error: Unsupported distribution" >&2
        echo "   Please install manually: libolm-dev, cmake, build-essential" >&2
        exit 1
    fi
}

build_from_source() {
    local project_dir
    project_dir=$(pwd)
    (
        set -e
        temp_dir=$(mktemp -d)
        trap 'rm -rf "$temp_dir"' EXIT

        cd "$temp_dir"

        echo "⬇ Downloading source..."
        wget "https://files.pythonhosted.org/packages/source/p/python-olm/${PYTHON_OLM_TARBALL}"

        echo "📦 Extracting..."
        tar -xzf "$PYTHON_OLM_TARBALL"
        cd "$PYTHON_OLM_DIR"

        # The bundled libolm declares cmake_minimum_required(VERSION 3.4). CMake
        # 4.x removed support for declaring requirements < 3.5, even though the
        # actual CMake features used are compatible.
        # We update to 3.5 to satisfy CMake 4.x's policy while maintaining
        # backward compatibility.
        echo "🩹 Patching CMakeLists.txt for modern CMake..."
        sed -i 's/cmake_minimum_required(VERSION [^)]*)/cmake_minimum_required(VERSION 3.5)/' \
            libolm/CMakeLists.txt

        echo "🔨 Building and installing..."
        VIRTUAL_ENV="${project_dir}/.venv" uv pip install .
    )
}

main "$@"
