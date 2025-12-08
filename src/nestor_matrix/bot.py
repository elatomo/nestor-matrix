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

        # Ignore events from the initial sync
        self.client.ignore_initial_sync = True
        # Ignore events that were sent while the bot was down
        self.client.ignore_first_sync = True

        # Register handlers
        self.client.add_event_handler(EventType.ROOM_MEMBER, self.handle_invite)
        self.client.add_event_handler(EventType.ROOM_MESSAGE, self.handle_message)

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

    async def handle_invite(self, event: StrippedStateEvent) -> None:
        """Auto-join invited rooms."""
        # Ignore the message if it's not an invitation for us.
        if (
            event.state_key == self.user_id
            and event.content.membership == Membership.INVITE  # type: ignore
        ):
            await self.client.join_room(event.room_id)
            logger.info("Joined room %s", event.room_id)

    async def handle_message(self, event: MessageEvent) -> None:
        logger.debug(
            "Message from %s in %s: %r",
            event.sender,
            event.room_id,
            event.content.body,
        )

        # Ignore our own messages
        if event.sender == self.user_id:
            return

        # Ignore replies to other messages
        if event.content.relates_to:
            return

        # # Only respond to mentions
        body = event.content.body
        if not self._is_mentioned(body):
            return

        # Echo message
        response = self._create_response(body)
        await self.client.send_message_event(
            event.room_id, EventType.ROOM_MESSAGE, response
        )

    def _is_mentioned(self, body: str) -> bool:
        """Check if bot is mentioned."""
        return body.startswith(("!nestor", settings.user_id))

    def _create_response(self, body: str) -> TextMessageEventContent:
        """Create echo response."""
        # Strip mention prefix
        text = body.split(maxsplit=1)[1] if " " in body else ""

        return TextMessageEventContent(
            msgtype=MessageType.NOTICE,
            body=text or "Hi! Mention me with a message.",
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
    bot = EchoBot()
    await bot.start()
