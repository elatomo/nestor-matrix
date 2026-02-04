"""Matrix client compatibility shims pending upstream."""

from mautrix.api import Method, Path
from mautrix.client import Client
from mautrix.errors import MatrixResponseError
from mautrix.types import (
    Event,
    PaginatedMessages,
    PaginationDirection,
    RelationType,
    SerializerError,
)


async def get_event_relations(
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
