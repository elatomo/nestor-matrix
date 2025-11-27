"""Command-line interface for Néstor Matrix bot."""

import asyncio
import logging
import sys

import click

logger = logging.getLogger("nestor_matrix")


@click.group()
@click.option("--debug", "-d", is_flag=True, help="Enable debug logging")
def cli(debug: bool):
    """Néstor Matrix bot."""
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)


@cli.command
@click.option("--homeserver", "-H", prompt=True, help="Homeserver domain or URL")
@click.option(
    "--username", "-u", prompt=True, help="Username (@user:domain or localpart)"
)
@click.option("--password", "-p", prompt=True, hide_input=True, help="Password")
def login(homeserver: str, username: str, password: str):
    """Get access token for bot authentication."""
    from .auth import get_access_token

    async def _login():
        try:
            token, device_id = await get_access_token(homeserver, username, password)
            click.echo("\n✓ Login successful!\n")
            click.echo("Add these to your .env file:\n")
            click.secho(f"HOMESERVER_URL={homeserver}", fg="green")
            click.secho(
                f"USER_ID={username if username.startswith('@') else f'@{username}:{homeserver}'}",
                fg="green",
            )
            click.secho(f"ACCESS_TOKEN={token}", fg="green")
            click.secho(f"DEVICE_ID={device_id}", fg="green")
        except Exception as e:
            click.secho(f"✗ Login failed: {e}", fg="red", err=True)
            sys.exit(1)

    asyncio.run(_login())


@cli.command()
@click.confirmation_option(
    prompt="⚠ This will log out your current device and invalidate your access token. Continue?"
)
def logout():
    """Log out from current device and invalidate access token.

    This deletes the device and its encryption keys from the homeserver.
    """
    from mautrix.client import Client

    from .config import settings

    async def _logout():
        client = None
        try:
            client = Client(
                mxid=settings.user_id,
                base_url=settings.homeserver_url,
                token=settings.access_token.get_secret_value(),
                device_id=settings.device_id,
            )
            await client.logout()

            click.secho(f"✓ Logged out from device '{settings.device_id}'", fg="green")
        except Exception as e:
            click.secho(f"✗ Failed: {e}", fg="red", err=True)
            sys.exit(1)
        finally:
            if client:
                client.stop()
                await client.api.session.close()

    asyncio.run(_logout())


@cli.command
def generate_pickle_key():
    """Generate crypto database encryption key.

    Generate a fresh symmetric encryption key to encrypt your bot's crypto keys
    at rest in the database.
    """
    import secrets

    click.echo(secrets.token_urlsafe(32))


@cli.command
def info():
    """Show bot configuration."""
    from .config import settings

    click.echo("Néstor Matrix Configuration:")
    click.echo(f"  Homeserver: {settings.homeserver_url}")
    click.echo(f"  User ID: {settings.user_id}")
    click.echo(f"  Device ID: {settings.device_id}")


if __name__ == "__main__":
    cli()
