"""Matrix bot main entry point."""

import logging

from markdown_it import MarkdownIt
from mautrix.client import Client
from mautrix.crypto import OlmMachine, PgCryptoStateStore, PgCryptoStore
from mautrix.types import (
    EventType,
    Format,
    Membership,
    MessageEvent,
    MessageType,
    StrippedStateEvent,
    TextMessageEventContent,
)
from mautrix.util.async_db import Database
from nestor import AssistantDeps, create_assistant_agent

from .config import settings

logger = logging.getLogger(__name__)

markdown = MarkdownIt()


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


def _extract_prompt(body: str) -> str:
    """Extract prompt from message, removing mention prefix."""
    return body.split(maxsplit=1)[1] if " " in body else ""


class NestorBot:
    """Néstor AI assistant bot with E2EE support."""

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

        # Néstor agent
        self.agent = create_assistant_agent(
            api_key=settings.nestor_openai_api_key,
            model_name=settings.nestor_default_model,
        )
        self.agent_deps = AssistantDeps(
            search_backend=settings.nestor_search_backend,
            safesearch=settings.nestor_safesearch,
        )

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

        # Get Néstor response
        prompt = _extract_prompt(event.content.body)
        if not prompt:
            await self._send_response(
                event.room_id,
                "Hi! Mention me with a message.",
            )
            return

        await self.client.set_typing(event.room_id, timeout=30_000)
        reply = "Sorry, I encountered an error processing your request."
        try:
            result = await self.agent.run(prompt, deps=self.agent_deps)
            reply = result.output
        except Exception:
            logger.exception("Failed to get AI response")
        finally:
            await self.client.set_typing(event.room_id, timeout=0)
            await self._send_response(event.room_id, reply)

    async def _send_response(self, room_id: str, text: str) -> None:
        """Send a markdown-formatted notice to a room."""
        content = TextMessageEventContent(
            msgtype=MessageType.NOTICE,
            format=Format.HTML,
            body=text,
            formatted_body=markdown.render(text),
        )
        await self.client.send_message_event(room_id, EventType.ROOM_MESSAGE, content)

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
    bot = NestorBot()
    await bot.start()
