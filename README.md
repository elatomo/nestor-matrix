<div align="center">
  <img src="https://raw.githubusercontent.com/elatomo/nestor-matrix/main/assets/avatar.png" alt="Néstor bot avatar" width="200">
</div>

# Néstor Matrix Bot

A Matrix bot for [Néstor](https://github.com/elatomo/nestor), a personal AI
assistant.

I run this on my own homeserver to learn about Matrix bots and have a simple
assistant available in my rooms. You're welcome to use it as reference or fork
it for your own experiments.

## Features

- Responds to mentions (`!nestor`, `!n`) in rooms or direct messages
- Threaded conversation memory
- End-to-end encryption support

## Quick Start

Requires Python 3.14 and [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/elatomo/nestor-matrix.git
cd nestor-matrix
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
## Usage

Invite the bot to a room and mention it:

```
!nestor what time is it in Tokyo?
```

Or message it directly (no mention needed in DMs).

## Development

```bash
make dev      # Install with dev dependencies
make check    # Run lints, types, tests
make shell    # Python REPL with project loaded
```

Run `make help` for all available commands.

## Deployment

Pushing to `main` triggers automatic deployment via GitHub Actions.

Server setup uses the script in `deploy/setup.sh`.
