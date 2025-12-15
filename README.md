<div align="center">
  <img src="https://raw.githubusercontent.com/elatomo/nestor-matrix/main/assets/avatar.png" alt="Néstor bot avatar" width="200">
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
cd nestor-matrix

# Install Python 3.14 (if needed)
# Option A: via asdf
asdf install

# Option B: via uv
uv python install

# Install dependencies
uv sync
```

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env

# Get access token and device ID
uv run nestor-matrix login

# Generate encryption key for crypto database
uv run nestor-matrix generate-pickle-key
```

Run the bot:

```bash
make run
```

## Deployment

Pushing to `main` triggers automatic deployment via GitHub Actions.

Server setup uses the script in `deploy/setup.sh`.
