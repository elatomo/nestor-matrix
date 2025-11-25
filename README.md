<div align="center">
  <img src="https://raw.githubusercontent.com/elatomo/nestor/main/assets/logo.png" alt="Néstor logo" width="300">
  <p><em>Matrix bot for <a href="https://github.com/elatomo/nestor">Néstor</a>, a personal AI assistant 🎩💬</em></p>
</div>

> [!CAUTION]
> Personal experiment in progress. Features may appear, disappear, or mutate
> without warning 🧪

## Quick Start

Néstor Matrix Bot requires Python 3.14 and [uv](https://github.com/astral-sh/uv).

```bash
# Clone the repository
git clone https://github.com/elatomo/nestor-matrix.git
cd nestor

# Install Python 3.14 (if needed)
# Option A: via asdf
asdf install

# Option B: via uv
uv python install

# Install dependencies
uv sync
```

### If python-olm fails to install

If you get a CMake-related error during installation:

```bash
sh scripts/install-python-olm.sh
uv sync --no-install-package python-olm
```

This happens when your CMake version is incompatible with the bundled libolm
build configuration. The script patches it for compatibility.

> [!NOTE]
> If you're affected by this issue and need to modify dependencies, use
> `sh scripts/generate-lock.sh` to regenerate the lock file. This script uses
> Docker with a compatible CMake version to ensure the lock can be generated
> successfully.
