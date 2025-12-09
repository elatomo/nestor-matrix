"""Matrix bot main entry point."""

import logging

from mautrix.client import Client
from mautrix.crypto import OlmMachine, PgCryptoStateStore, PgCryptoStore
from mautrix.types import (
    EventType,
    Membership,
    MessageEvent,
    MessageType,
    StrippedStateEvent,
    TextMessageEventContent,
)
from mautrix.util.async_db import Database

from .config import settings

logger = logging.getLogger(__name__)


def _is_mentioned(body: str, user_id: str) -> bool:
    """Check if bot is mentioned in message."""
    return body.startswith(("!nestor", "!n", user_id))


def _should_ignore_message(event: MessageEvent, bot_user_id: str) -> bool:
    """Check if message should be ignored."""
    return (
        # Ignore our own messages
        event.sender == bot_user_id
        # Ignore replies to other messages
        or bool(event.content.relates_to)
    )


def _create_echo_response(body: str) -> TextMessageEventContent:
    """Create echo response from message body."""
    # Strip mention prefix
    text = body.split(maxsplit=1)[1] if " " in body else ""
    return TextMessageEventContent(
        msgtype=MessageType.NOTICE,
        body=text or "Hi! Mention me with a message.",
    )


class EchoBot:
    """Simple echo bot with E2EE support."""

    def __init__(self):
        # Database for crypto + state
        self.db = Database.create(settings.database_url)

        self.crypto_store = PgCryptoStore(
            account_id=settings.user_id,
            pickle_key=settings.pickle_key.get_secret_value(),
            db=self.db,
        )
        self.state_store = PgCryptoStateStore(self.db)

        self.client = Client(
            mxid=settings.user_id,
            base_url=settings.homeserver_url,
            token=settings.access_token.get_secret_value(),
            device_id=settings.device_id,
            state_store=self.state_store,
        )

        # Crypto machine
        self.client.crypto = OlmMachine(
            self.client,
            self.crypto_store,
            self.state_store,
        )

        self.user_id = settings.user_id

        self.client.ignore_initial_sync = settings.ignore_initial_sync
        self.client.ignore_first_sync = settings.ignore_first_sync

        # Register handlers
        self.client.add_event_handler(EventType.ROOM_MEMBER, self._handle_invite)
        self.client.add_event_handler(EventType.ROOM_MESSAGE, self._handle_message)

    async def start(self):
        """Start the bot."""
        logger.info("Starting bot")

        logger.debug("Starting database")
        await self.db.start()

        logger.debug("Ensuring crypto tables exist")
        await self.crypto_store.upgrade_table.upgrade(self.db)
        await self.state_store.upgrade_table.upgrade(self.db)

        logger.debug("Opening crypto store")
        await self.crypto_store.open()

        logger.debug("Loading crypto machine")
        await self.client.crypto.load()

        logger.debug("Connecting to homeserver")
        whoami = await self.client.whoami()
        logger.info(
            "Connected, I'm %s using device %s", whoami.user_id, whoami.device_id
        )

        try:
            await self.client.start(None)
        finally:
            await self._cleanup()

    async def _handle_invite(self, event: StrippedStateEvent) -> None:
        """Auto-join invited rooms."""
        # Ignore the message if it's not an invitation for us.
        if (
            event.state_key == self.user_id
            and event.content.membership == Membership.INVITE  # type: ignore
        ):
            await self.client.join_room(event.room_id)
            logger.info("Joined room %s", event.room_id)

    async def _handle_message(self, event: MessageEvent) -> None:
        logger.debug(
            "Message from %s in %s: %r",
            event.sender,
            event.room_id,
            event.content.body,
        )

        if _should_ignore_message(event, self.user_id):
            return

        if not _is_mentioned(event.content.body, self.user_id):
            return

        # Echo message
        response = _create_echo_response(event.content.body)
        await self.client.send_message_event(
            event.room_id, EventType.ROOM_MESSAGE, response
        )

    async def _cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("Cleaning up")
        self.client.stop()
        await self.client.api.session.close()
        await self.crypto_store.close()
        await self.db.stop()
        logger.info("Cleanup complete")


async def main():
    """Create and start the bot."""
    bot = EchoBot()
    await bot.start()
