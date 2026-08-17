from datetime import UTC, datetime

from intelligent_email_service.email_connectors.mock_graph import MockGraphProvider
from intelligent_email_service.retrieval.thread_processor import ThreadProcessor


def test_mock_graph_filter_by_date_resilience():
    messages = [
        {"id": "1", "receivedDateTime": "2026-07-30T10:00:00Z"},
        {"id": "2", "receivedDateTime": "invalid-timestamp"},
        {"id": "3", "receivedDateTime": None},
    ]

    start = datetime(2026, 7, 1, tzinfo=UTC)
    end = datetime(2026, 7, 31, tzinfo=UTC)

    filtered = MockGraphProvider._filter_by_date(messages, start, end)
    assert len(filtered) == 1
    assert filtered[0]["id"] == "1"


def test_thread_processor_is_full_quoted_html():
    html_message = {
        "id": "msg-html",
        "subject": "Re: Portfolio Review",
        "body": {
            "contentType": "html",
            "content": (
                "<div>I approve the rebalancing.</div>"
                "<div id='divRplyFwdMsg'>"
                "<b>From:</b> Jane Doe &lt;jane@example.com&gt;<br>"
                "<b>Sent:</b> Tuesday, July 28, 2026 3:00 PM<br>"
                "<b>Subject:</b> Re: Portfolio Review"
                "</div>"
            ),
        },
    }

    assert ThreadProcessor._is_full_quoted(html_message) is True


def test_dag_reconstructor_empty_list():
    from intelligent_email_service.retrieval.reconstructors import (
        GraphConversationReconstructor,
    )

    reconstructor = GraphConversationReconstructor()
    assert reconstructor.reconstruct([]) == []


def test_dag_reconstructor_cycle_detection():
    """Validates that cyclic references (A -> B -> A) do not cause infinite recursion."""
    from intelligent_email_service.retrieval.email_node import EmailNode
    from intelligent_email_service.retrieval.reconstructors import (
        GraphConversationReconstructor,
    )

    reconstructor = GraphConversationReconstructor()
    t1 = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    t2 = datetime(2026, 8, 1, 11, 0, tzinfo=UTC)

    node_a = EmailNode(
        id="node-a",
        message_id="msg-a",
        in_reply_to="msg-b",
        received_at=t1,
        subject="Cycle Test",
    )
    node_b = EmailNode(
        id="node-b",
        message_id="msg-b",
        in_reply_to="msg-a",
        received_at=t2,
        subject="Cycle Test",
    )

    result = reconstructor.reconstruct([node_a, node_b])
    assert len(result) == 2
    assert {n.id for n in result} == {"node-a", "node-b"}


def test_dag_reconstructor_orphan_parent_missing():
    """Validates that replies pointing to non-existent parent IDs are safely retained."""
    from intelligent_email_service.retrieval.email_node import EmailNode
    from intelligent_email_service.retrieval.reconstructors import (
        GraphConversationReconstructor,
    )

    reconstructor = GraphConversationReconstructor()
    t1 = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    t2 = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    node1 = EmailNode(
        id="node-1",
        message_id="msg-1",
        in_reply_to="non-existent-msg-id",
        received_at=t1,
        subject="Orphan 1",
    )
    node2 = EmailNode(
        id="node-2",
        message_id="msg-2",
        in_reply_to="msg-1",
        received_at=t2,
        subject="Reply to Orphan",
    )

    result = reconstructor.reconstruct([node1, node2])
    assert len(result) == 2
    assert result[0].id == "node-1"
    assert result[1].id == "node-2"


def test_dag_reconstructor_branching_tree():
    """Validates branching replies where two messages reply to the same root."""
    from intelligent_email_service.retrieval.email_node import EmailNode
    from intelligent_email_service.retrieval.reconstructors import (
        GraphConversationReconstructor,
    )

    reconstructor = GraphConversationReconstructor()
    t0 = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    t2 = datetime(2026, 8, 1, 11, 0, tzinfo=UTC)
    t3 = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    root = EmailNode(id="root", message_id="root-msg", received_at=t0, subject="Topic")
    branch_a = EmailNode(
        id="b_a",
        message_id="b_a_msg",
        in_reply_to="root-msg",
        received_at=t1,
        subject="Topic",
    )
    branch_b = EmailNode(
        id="b_b",
        message_id="b_b_msg",
        in_reply_to="root-msg",
        received_at=t2,
        subject="Topic",
    )
    reply_to_a = EmailNode(
        id="rep_a",
        message_id="rep_a_msg",
        in_reply_to="b_a_msg",
        received_at=t3,
        subject="Topic",
    )

    result = reconstructor.reconstruct([root, branch_b, branch_a, reply_to_a])
    assert len(result) == 4
    assert result[0].id == "root"
    assert result[1].id == "b_a"
    assert result[2].id == "rep_a"
    assert result[3].id == "b_b"

