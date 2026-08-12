"""End-to-end driver pipeline for Intelligent Email Service."""

import asyncio
import json
import logging
import sys
import warnings
from dataclasses import asdict
from pathlib import Path

from .config import EmailQueryFilter, PipelineConfig
from .email_connectors import EmailProvider, MockGraphProvider
from .exceptions import EmailProviderError
from .logging_config import setup_logging
from .preprocessing import EmailCleaner, EmailCompressor
from .preprocessing.compressor import CompressedThread
from .retrieval import EmailRetrievalService, ThreadProcessor, process_node_attachments

warnings.filterwarnings("ignore", category=RuntimeWarning, module="runpy")


logger = logging.getLogger(__name__)


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

    setup_logging(level=config.log_level)

    logger.info(
        "Starting pipeline for advisor '%s' & client '%s' (log_level: %s)...",
        query.advisor_id,
        query.client_id,
        config.log_level,
    )

    if provider is None:
        if config.app_env in ("test_prod", "prod", "production"):
            from .email_connectors import MicrosoftGraphProvider

            provider = MicrosoftGraphProvider.from_env(config=config.graph)
        else:
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

    # Step 4: Attachment Extraction & Preprocessing
    cleaner = EmailCleaner(config=config.cleaner)
    for thread in processed_threads:
        for node in thread.messages:
            await process_node_attachments(
                provider=provider, user_id=query.advisor_id, node=node
            )
        thread.messages = await cleaner.clean_messages_async(thread.messages)

    # Step 5: Context Compression (LLMLingua neural prompt compression / character truncation)
    compressor = EmailCompressor(config=config.compressor)

    return [compressor.compress_processed_thread(thread) for thread in processed_threads]


ARGV_CLIENT_ID_INDEX: int = 2


async def main() -> None:
    """Executable CLI entry point for running the pipeline in isolation."""
    advisor_id = sys.argv[1] if len(sys.argv) > 1 else "tst_ad-001"
    client_id = (
        sys.argv[ARGV_CLIENT_ID_INDEX]
        if len(sys.argv) > ARGV_CLIENT_ID_INDEX
        else "jane.household@example-clients.com"
    )

    print(f"Executing pipeline for Advisor '{advisor_id}' & Client '{client_id}'...")

    query = EmailQueryFilter(advisor_id=advisor_id, client_id=client_id)
    config = PipelineConfig()

    try:
        threads = await process_client_emails(query=query, config=config)

        print(f"\nProcessing complete. Total Thread(s): {len(threads)}")
        for idx, thread in enumerate(threads, start=1):
            print(f"\n--- Subject #{idx}: {thread.subject} ---")
            print(f"  Conversation ID: {thread.conversation_id}")
            print(f"  Total Messages:  {thread.total_messages}")
            print(f"  Est. Tokens:     {thread.estimated_tokens}")
            print(f"  Attachments:     {len(thread.attachments_summary)}")

        with Path("compressed_threads.json").open("w") as f:
            json.dump([asdict(thread) for thread in threads], f, indent=2, default=str)
            print("\nCompressed threads saved to 'compressed_threads.json'.")
    except EmailProviderError as err:
        print(f"\n[Provider Error] {err}")
        print(
            "Note: Default MockGraphProvider connects to 'http://localhost:3000'. "
            "Ensure your Mockoon server is running or pass a custom EmailProvider."
        )


if __name__ == "__main__":
    asyncio.run(main())
