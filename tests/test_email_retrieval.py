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
