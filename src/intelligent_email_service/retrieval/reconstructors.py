"""Thread reconstruction strategies using Protocol interface."""

from collections import defaultdict
from datetime import datetime
from typing import Protocol, runtime_checkable

from .email_node import EmailNode


@runtime_checkable
class ConversationReconstructor(Protocol):
    """Strategy Protocol for email thread reconstruction."""

    def reconstruct(self, nodes: list[EmailNode]) -> list[EmailNode]:
        """Reconstructs and orders email nodes into a coherent thread."""
        ...


class GraphConversationReconstructor:
    """Default Strategy: In-memory DAG using parent message references."""

    def reconstruct(self, nodes: list[EmailNode]) -> list[EmailNode]:
        if not nodes:
            return []

        # Index nodes by Message-ID and ID for O(1) parent lookup
        lookup = {n.message_id: n for n in nodes if n.message_id} | {n.id: n for n in nodes if n.id}

        children: dict[str, list[EmailNode]] = defaultdict(list)
        roots: list[EmailNode] = []

        for node in nodes:
            parent = lookup.get(node.in_reply_to) if node.in_reply_to else None
            if parent:
                children[parent.id].append(node)
            else:
                roots.append(node)

        ordered: list[EmailNode] = []

        def dfs(curr: EmailNode) -> None:
            ordered.append(curr)
            for child in sorted(children[curr.id], key=lambda x: x.received_at or datetime.min):
                dfs(child)

        for root in sorted(roots, key=lambda x: x.received_at or datetime.min):
            dfs(root)

        return ordered


class LinearConversationReconstructor:
    """Fallback Strategy: Chronological timestamp sorting."""

    def reconstruct(self, nodes: list[EmailNode]) -> list[EmailNode]:
        return sorted(nodes, key=lambda n: n.received_at or datetime.min)
