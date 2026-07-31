"""End-to-end driver pipeline for Intelligent Email Service."""

import asyncio
import sys
import warnings

warnings.filterwarnings("ignore", category=RuntimeWarning, module="runpy")

from .config import EmailQueryFilter, PipelineConfig
from .email_connectors import EmailProvider, MockGraphProvider
from .exceptions import EmailProviderError
from .preprocessing import EmailCleaner, EmailCompressor
from .preprocessing.compressor import CompressedThread
from .retrieval import EmailRetrievalService, ThreadProcessor


async def process_client_emails(
    query: EmailQueryFilter,
    provider: EmailProvider | None = None,
    config: PipelineConfig | None = None,
) -> list[CompressedThread]:
    """
    End-to-end pipeline driver for processing client emails from an advisor's mailbox.

    Accepts structured EmailQueryFilter and PipelineConfig objects.

    Pipeline Steps:
      1. Retrieval: Fetch and filter advisor's emails matching client_id.
      2. Grouping: Group matched emails by normalized subject line.
      3. Thread Reconstruction: Reconstruct modified & full-quoted threads via ThreadProcessor.
      4. Preprocessing: Clean HTML and strip email signatures via EmailCleaner.
      5. Context Compression: Compress historical messages via EmailCompressor (LLMLingua / truncation).

    Returns:
      A list of CompressedThread objects ready for downstream LLM context window injection.
    """
    if config is None:
        config = PipelineConfig()

    if provider is None:
        provider = MockGraphProvider()

    # Step 1 & 2: Retrieval and Subject Grouping
    retrieval_service = EmailRetrievalService(provider=provider)
    subject_groups = await retrieval_service.get_client_email_groups(
        advisor_id=query.advisor_id,
        client_id=query.client_id,
        start_date=query.start_date,
        end_date=query.end_date,
    )

    if not subject_groups:
        return []

    # Step 3: Thread Reconstruction (handles FULL_QUOTED and MODIFIED formats)
    processor = ThreadProcessor(
        provider=provider,
        user_id=query.advisor_id,
        client_id=query.client_id,
        max_concurrency=config.max_concurrency,
    )
    processed_threads = await processor.process_subject_groups(subject_groups)

    # Step 4: Preprocessing & Cleaning (HTML stripping & signature removal)
    cleaner = EmailCleaner(config=config.cleaner)
    for thread in processed_threads:
        thread.messages = [cleaner.clean_message(msg) for msg in thread.messages]

    # Step 5: Context Compression (LLMLingua neural prompt compression / character truncation)
    compressor = EmailCompressor(config=config.compressor)

    return [compressor.compress_processed_thread(thread) for thread in processed_threads]


async def main() -> None:
    """Executable CLI entry point for running the pipeline in isolation."""
    advisor_id = sys.argv[1] if len(sys.argv) > 1 else "tst_ad-001"
    client_id = sys.argv[2] if len(sys.argv) > 2 else "jane.household@example-clients.com"

    print(f"Executing pipeline for Advisor '{advisor_id}' & Client '{client_id}'...")

    query = EmailQueryFilter(advisor_id=advisor_id, client_id=client_id)
    config = PipelineConfig()

    try:
        threads = await process_client_emails(query=query, config=config)

        print(f"\nProcessing complete. Total Thread(s): {len(threads)}")
        for idx, thread in enumerate(threads, start=1):
            print(f"\n--- Thread #{idx}: {thread.subject} ---")
            print(f"  Conversation ID: {thread.conversation_id}")
            print(f"  Total Messages:  {thread.total_messages}")
            print(f"  Est. Tokens:     {thread.estimated_tokens}")
            print(f"  Attachments:     {len(thread.attachments_summary)}")
    except EmailProviderError as err:
        print(f"\n[Provider Error] {err}")
        print(
            "Note: Default MockGraphProvider connects to 'http://localhost:3000'. "
            "Ensure your Mockoon server is running or pass a custom EmailProvider."
        )


if __name__ == "__main__":
    asyncio.run(main())
