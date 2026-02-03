"""Matrix bot main entry point."""

import logging

from markdown_it import MarkdownIt
from mautrix.api import Method, Path
from mautrix.client import Client
from mautrix.crypto import OlmMachine, PgCryptoStateStore, PgCryptoStore
from mautrix.errors import DecryptionError, MatrixResponseError, SessionNotFound
from mautrix.types import (
    Event,
    EventType,
    Format,
    InReplyTo,
    Membership,
    MessageEvent,
    MessageType,
    PaginatedMessages,
    PaginationDirection,
    RelatesTo,
    RelationType,
    SerializerError,
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
    return body.lower().startswith(("!nestor", "!n", user_id))


def _extract_prompt(body: str) -> str:
    """Extract prompt from message, removing mention prefix."""
    return body.split(maxsplit=1)[1] if " " in body else ""


async def _get_event_relations(
    client: Client,
    room_id: str,
    event_id: str,
    rel_type: RelationType | None = None,
    direction: PaginationDirection = PaginationDirection.BACKWARD,
    from_token: str | None = None,
    to_token: str | None = None,
    limit: int | None = None,
) -> PaginatedMessages:
    """Get child events for a given parent event.

    See https://spec.matrix.org/v1.17/client-server-api/#relationships-api

    NOTE: Not yet in mautrix-python (see PR
    https://github.com/mautrix/python/pull/157)

    Args:
        client: The Matrix client.
        room_id: The room containing the parent event.
        event_id: The parent event ID.
        rel_type: Filter by relation type (e.g., THREAD).
        direction: FORWARD for chronological, BACKWARD for reverse.
            Pagination starts at `from_token` (or most recent if omitted).
        from_token: Pagination token to start from.
        to_token: Pagination token to stop at.
        limit: Maximum number of events to return.

    Returns:
        PaginatedMessages with events and pagination tokens.
    """
    query_params = {
        "dir": direction.value,
        "from": from_token,
        "to": to_token,
        "limit": str(limit) if limit else None,
    }

    content = await client.api.request(
        method=Method.GET,
        path=(
            Path.v1.rooms[room_id].relations[event_id][rel_type.value]
            if rel_type
            else Path.v1.rooms[room_id].relations[event_id]
        ),
        query_params=query_params,  # type: ignore
        metrics_method="getRelations",
    )

    try:
        return PaginatedMessages(  # type: ignore
            start=content.get("prev_batch"),
            end=content.get("next_batch"),
            events=[Event.deserialize(event) for event in content["chunk"]],
        )
    except KeyError:
        raise MatrixResponseError("`chunk` not in response.")
    except SerializerError as e:
        raise MatrixResponseError("Invalid events in response") from e


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

    async def _is_direct_message(self, room_id: str) -> bool:
        """Check if room is a DM (exactly 2 members)."""
        return len(await self.client.get_joined_members(room_id)) == 2

    async def _should_respond(self, event: MessageEvent) -> bool:
        """Determine if bot should respond to this message."""
        # Ignore our own messages
        if event.sender == self.user_id:
            return False

        if await self._is_direct_message(event.room_id):
            return True

        return _is_mentioned(event.content.body, self.user_id)

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

        if not await self._should_respond(event):
            return

        # Get Néstor response
        prompt = (
            _extract_prompt(event.content.body)
            if _is_mentioned(event.content.body, self.user_id)
            else event.content.body
        )
        if not prompt:
            await self._reply_in_thread(event, "Hi! Mention me with a message.")
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
            await self._reply_in_thread(event, reply)

    async def _reply_in_thread(self, event: MessageEvent, text: str) -> None:
        """Reply to an event, rendering text as Markdown."""
        content = TextMessageEventContent(
            msgtype=MessageType.NOTICE,
            format=Format.HTML,
            body=text,
            formatted_body=markdown.render(text),
            relates_to=RelatesTo(
                rel_type=RelationType.THREAD,
                event_id=event.content.relates_to.event_id or event.event_id,
                is_falling_back=True,
                in_reply_to=InReplyTo(event_id=event.event_id),
            ),
        )
        await self.client.send_message_event(
            event.room_id, EventType.ROOM_MESSAGE, content
        )

    async def _get_thread_messages(
        self, room_id: str, thread_root_id: str, limit: int = 10
    ) -> list[MessageEvent]:
        """Fetch and decrypt most recent messages from a thread (newest-first)."""
        response = await _get_event_relations(
            self.client,
            room_id=room_id,
            event_id=thread_root_id,
            rel_type=RelationType.THREAD,
            limit=limit,
        )

        events: list[MessageEvent] = []
        for event in response.events:  # type: ignore
            try:
                decrypted = await self._decrypt_event_if_needed(event)
                if isinstance(decrypted, MessageEvent):
                    events.append(decrypted)
            except SessionNotFound:
                # Message from before we joined or different device
                logger.debug(
                    "Skipping event %s: missing decryption session", event.event_id
                )
            except DecryptionError as e:
                logger.warning("Failed to decrypt event %s: %s", event.event_id, e)

        return events

    async def _decrypt_event_if_needed(self, event: Event) -> Event:
        """Decrypt event if it's encrypted."""
        if event.type == EventType.ROOM_ENCRYPTED:
            return await self.client.crypto.decrypt_megolm_event(event)
        return event

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
