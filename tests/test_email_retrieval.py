import asyncio

from intelligent_email_service.email_connectors.mock_graph import MockGraphProvider
from intelligent_email_service.retrieval.email_retrieval import EmailRetrievalService
from intelligent_email_service.retrieval.thread_processor import (
    ThreadFormat,
    ThreadProcessor,
)

MOCK_BASE_URL = "http://localhost:3000"


async def main():
    advisor_id = input("Enter the advisor_id: ").strip()
    client_id = input("Enter the client_id: ").strip()

    provider = MockGraphProvider(base_url=MOCK_BASE_URL)
    retrieval_service = EmailRetrievalService(provider=provider)
    thread_processor = ThreadProcessor(
        provider=provider, user_id=advisor_id, client_id=client_id
    )

    print("==" * 80)
    print("Retrieving client Emails")
    print("==" * 80)

    client_messages = await retrieval_service.get_client_emails(
        advisor_id=advisor_id, client_id=client_id
    )
    print(f"Retrieved {len(client_messages)} messages for client: {client_id}")

    print("\n" + "==" * 80)
    print("Grouping by Subject")
    print("==" * 80)

    subject_groups = retrieval_service._group_by_subject(client_messages)
    print(f"Found {len(subject_groups)} subjects")

    for subject, messages in subject_groups.items():
        print(f"Subject: {subject}")
        print(f"Messages: {messages}")

    print("\n" + "==" * 80)
    print("Processing Threads")
    print("==" * 80)

    subjects = list(subject_groups.keys())
    results = await asyncio.gather(
        *(
            thread_processor.process_subject_group(messages=messages)
            for messages in subject_groups.values()
        )
    )
    processed_threads = []
    for subject, processed_thread in zip(subjects, results):
        print(f"Processing subject: {subject}")

        if not processed_thread:
            print("No thread returned")
            continue
        processed_threads.append(processed_thread)
        print(f"Format: {processed_thread.format.value}")
        print(f"Conversation ID: {processed_thread.conversation_id}")
        print(f"Messages: {len(processed_thread.messages)}")
        print("Chronological Order: ")

        for ind, message in enumerate(processed_thread.messages, start=1):
            sender = (
                message.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
            )
            timestamp = message.get("receivedDateTime") or message.get("recievedDateTime", "Unknown")
            print(f"{ind}, {timestamp} | {sender}")

    print("\n", "==" * 80)
    print("Final Summary")
    print("==" * 80)

    full_quoted_count = sum(
        1 for t in processed_threads if t.format == ThreadFormat.FULL_QUOTED
    )
    modified_count = sum(
        1 for t in processed_threads if t.format == ThreadFormat.MODIFIED
    )

    print(f"Client: {client_id}")
    print(f"Subject groups: {len(processed_threads)}")
    print(f"Full quoted threads: {full_quoted_count}")
    print(f"Modified threads: {modified_count}")


if __name__ == "__main__":
    asyncio.run(main())


def test_mock_graph_filter_by_date_resilience():
    from datetime import datetime, UTC

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


