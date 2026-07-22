import argparse
import asyncio

from intelligent_email_service.email_connectors import MockGraphProvider
from intelligent_email_service.retrieval.email_retrieval import EmailRetrievalService


def parse_args():
    parser = argparse.ArgumentParser(
        description="Test email retrieval and subject grouping"
    )
    parser.add_argument(
        "--base_url", default="http://localhost:3000", help="Mockoon base url"
    )
    parser.add_argument(
        "--advisor-id", default="tst_ad-001", help="Advisor ID [tst_ad-001, tst_ad-XX]"
    )
    parser.add_argument(
        "--client-id", help="Client Email Address [firstname.lastname@example.com]"
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    provider = MockGraphProvider(base_url=args.base_url)
    ret_service = EmailRetrievalService(provider=provider)

    print("=" * 70)
    print("EMAIL RETRIEVAL TEST")
    print("=" * 70)
    print(f"Advisor:    {args.advisor_id}")
    print(f"Client:     {args.client_id}")

    if not args.client_id:
        print("\nError: --client-id is required to retrieve client emails.")
        return

    raw_emails = await ret_service.get_client_emails(
        advisor_id=args.advisor_id,
        client_id=args.client_id,
    )

    email_groups = EmailRetrievalService._group_by_subject(raw_emails)

    print("\n" + "=" * 70)
    print("RETRIEVAL RESULTS")
    print("=" * 70)

    if not email_groups:
        print("No emails found.")
        return

    total_messages = sum(len(messages) for messages in email_groups.values())

    print(f"Subject Groups: {len(email_groups)}")
    print(f"Total Messages: {total_messages}")

    # ---------------------------------------------------------
    # Print each subject group
    # ---------------------------------------------------------
    for index, (subject, messages) in enumerate(
        email_groups.items(),
        start=1,
    ):
        print("\n" + "-" * 70)
        print(f"GROUP {index}")
        print("-" * 70)

        print(f"Normalized Subject: {subject}")
        print(f"Messages: {len(messages)}")

        for message_index, message in enumerate(
            messages,
            start=1,
        ):
            sender = (message.get("from") or {}).get("emailAddress") or {}

            sender_name = sender.get(
                "name",
            ) or "Unknown"

            sender_email = sender.get(
                "address",
            ) or "Unknown"

            print(f"\nMessage {message_index}:")
            print(f"  ID: {message.get('id')}")
            print(f"  Conversation ID: {message.get('conversation_id')}")
            print(f"  Subject: {message.get('subject')}")
            print(f"  Sender: {sender_name} <{sender_email}>")
            print(f"  Received: {message.get('receivedDateTime')}")


if __name__ == "__main__":
    asyncio.run(main())
