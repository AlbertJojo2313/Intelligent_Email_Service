"""Thread reconstruction strategies using Protocol interface."""

from collections import defaultdict
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from .email_node import EmailNode


@runtime_checkable
class ConversationReconstructor(Protocol):
    """Strategy Protocol for email thread reconstruction."""

    def reconstruct(self, nodes: list[EmailNode]) -> list[EmailNode]:
        """Reconstructs and orders email nodes into a coherent thread."""
        ...


class GraphConversationReconstructor:
    """Default Strategy: In-memory DAG using parent message references (In-Reply-To / Message-ID)."""

    def reconstruct(self, nodes: list[EmailNode]) -> list[EmailNode]:
        if not nodes:
            return []

        min_utc_date = datetime.min.replace(tzinfo=UTC)

        # Index nodes by Message-ID and ID for O(1) parent lookup
        lookup = {n.message_id: n for n in nodes if n.message_id} | {
            n.id: n for n in nodes if n.id
        }

        children: dict[str, list[EmailNode]] = defaultdict(list)
        roots: list[EmailNode] = []

        for node in nodes:
            parent = (
                lookup.get(node.in_reply_to)
                if node.in_reply_to and node.in_reply_to not in (node.id, node.message_id)
                else None
            )
            if parent:
                children[parent.id].append(node)
            else:
                roots.append(node)

        ordered: list[EmailNode] = []
        visited: set[int] = set()

        def dfs(curr: EmailNode) -> None:
            obj_id = id(curr)
            if obj_id in visited:
                return
            visited.add(obj_id)
            ordered.append(curr)
            for child in sorted(
                children[curr.id], key=lambda x: x.received_at or min_utc_date
            ):
                dfs(child)

        for root in sorted(roots, key=lambda x: x.received_at or min_utc_date):
            dfs(root)

        remaining = [n for n in nodes if id(n) not in visited]
        if remaining:
            ordered.extend(sorted(remaining, key=lambda x: x.received_at or min_utc_date))

        return ordered


class LinearConversationReconstructor:
    """Dev Strategy: Chronological timestamp sorting fallback for mock testing."""

    def reconstruct(self, nodes: list[EmailNode]) -> list[EmailNode]:
        min_utc_date = datetime.min.replace(tzinfo=UTC)
        return sorted(nodes, key=lambda n: n.received_at or min_utc_date)
