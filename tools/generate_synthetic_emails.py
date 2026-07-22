import argparse
import asyncio
import json
import os
import random
from pathlib import Path

from dotenv import load_dotenv
from faker import Faker
from synthetic_generator import (
    ClientPool,
    ClientProfile,
    NvidiaClient,
    SyntheticEmailGenerator,
)
from synthetic_generator.generator import AdvisorProfile, EmailGenerationConfig

## Default Constants
DEFAULT_NUM_CLIENTS = 5

load_dotenv()

fake = Faker()

# Predefined templates for rule-based fallback
FALLBACK_TEMPLATES = {
    "portfolio_rebalancing": [
        "Hi {advisor_name},\n\nI was looking at my portfolio and noticed we have a lot of cash. Should we rebalance it into the mutual funds we discussed?\n\nBest,\n{client_name}",
        "Hello {client_name},\n\nThanks for reaching out. Yes, we should deploy that cash. I will prepare a rebalancing proposal and send it over for your signature today.\n\nBest,\n{advisor_name}",
        "Great, thanks! I'll keep an eye out for that document.\n\nBest,\n{client_name}",
    ],
    "ira_contributions": [
        "Dear {advisor_name},\n\nCan you check how much I can still contribute to my Roth IRA for this year? I want to make sure I don't go over the limit.\n\nRegards,\n{client_name}",
        "Hi {client_name},\n\nFor 2026, the contribution limit is $7,000 (or $8,000 if you are 50 or older). You have contributed $4,500 so far, so you can add up to $2,500.\n\nBest,\n{advisor_name}",
        "Thank you! I will transfer the remaining $2,500 today.\n\nRegards,\n{client_name}",
    ],
    "onboarding_documents": [
        "Hi {advisor_name},\n\nI wanted to check what documents you still need from us to finish our onboarding. We sent the driver's licenses yesterday.\n\nBest,\n{client_name}",
        "Hi {client_name},\n\nThank you for the licenses. To finalize, we still need the signed advisory agreement and a copy of your most recent brokerage statement.\n\nRegards,\n{advisor_name}",
        "Got it. I will upload those to the portal tonight.\n\nBest,\n{client_name}",
    ],
    "default": [
        "Hi {advisor_name},\n\nJust checking in regarding our conversation about my accounts. Is there any update on the setup?\n\nBest,\n{client_name}",
        "Hello {client_name},\n\nYes, the account setup is complete. You should receive a welcome email with login details shortly.\n\nBest,\n{advisor_name}",
    ],
}


def load_topics():
    topics_path = Path(__file__).parent / "topics.json"
    if Path.exists(topics_path):
        try:
            with Path.open(topics_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading topics.json: {e}. Using fallback keys.")
    return list(FALLBACK_TEMPLATES.keys())


# Checker
def _ensure_client_pool(args):
    # If the user explicitly sets --num-clients 1 or provides specific client details, respect it.
    is_client_overridden = (
        args.client_name != "Sarah Client" or args.client_email != "client@example.com"
    )
    if (args.num_clients <= 1) or (
        is_client_overridden
        and args.num_clients == DEFAULT_NUM_CLIENTS
        and args.client_pool is None
    ):
        # Fall back to single custom client if explicitly configured
        client_pool = ClientPool(size=1, faker_instance=fake)
        # Manually overwrite the generated single client with CLI parameters
        client_pool.clients = [
            ClientProfile(name=args.client_name, email=args.client_email)
        ]
        print(f"Using single client: {args.client_name} <{args.client_email}>")
    else:
        client_pool = ClientPool(
            size=args.num_clients,
            custom_pool_path=args.client_pool,
            faker_instance=fake,
        )
        print(f"Initialized client pool with {len(client_pool.clients)} clients.")
    return client_pool


# Returns parser config
def _parser_config():
    parser = argparse.ArgumentParser(
        description="Generate synthetic emails for Mockoon / testing"
    )
    parser.add_argument(
        "--output",
        default="mock_emails.json",
        help="Path to write the output JSON file",
    )
    parser.add_argument(
        "--conversations",
        type=int,
        default=5,
        help="Number of conversation threads to generate",
    )

    # Advisor Configuration
    parser.add_argument(
        "--advisor-email",
        default="advisor@example.com",
        help="Email of the financial advisor",
    )
    parser.add_argument(
        "--advisor-name", default="John Advisor", help="Name of the financial advisor"
    )

    # Client Configuration (used when generating a single client or loading defaults)
    parser.add_argument(
        "--client-email",
        default="client@example.com",
        help="Email of the client (for single-client fallback)",
    )
    parser.add_argument(
        "--client-name",
        default="Sarah Client",
        help="Name of the client (for single-client fallback)",
    )
    parser.add_argument(
        "--num-clients",
        type=int,
        default=5,
        help="Number of distinct clients to generate in the pool",
    )
    parser.add_argument(
        "--client-pool",
        default=None,
        help="Path to a JSON file containing a predefined pool of clients",
    )

    # Email Gen_Config
    parser.add_argument(
        "--thread-format",
        choices=["full_quoted", "modified"],
        default="full_quoted",
        help=(
            "Email thread formatting mode. "
            "'full_quoted' includes previous messages as quoted history "
            "in every reply; 'modified' contains only the new message content"
        ),
    )

    # NVIDIA LLM Configuration
    parser.add_argument(
        "--nvidia-key",
        default=os.getenv("NVIDIA_API_KEY"),
        help="NVIDIA API key (defaults to NVIDIA_API_KEY environment variable)",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("NVIDIA_MODEL"),
        help="NVIDIA model to use",
    )
    parser.add_argument(
        "--url",
        default=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        help="NVIDIA API base URL",
    )
    return parser


async def main():
    # Load parser configs
    parser = _parser_config()

    args = parser.parse_args()
    topics = load_topics()

    # 1. Initialize the Client Pool
    client_pool = _ensure_client_pool(args)

    # 2. Initialize NVIDIA LLM Client (if API Key is configured)
    nvidia_key = args.nvidia_key or os.getenv("NVIDIA_API_KEY")
    llm_client = None
    if nvidia_key:
        llm_client = NvidiaClient(api_key=nvidia_key, model=args.model, base_url=args.url)
    else:
        print(
            "Warning: --nvidia-key (or NVIDIA_API_KEY env var) is missing. Falling back to template-based generation."
        )

    # 3. Initialize Orchestrator
    generator = SyntheticEmailGenerator(
        advisor=AdvisorProfile(
            name=args.advisor_name,
            email=args.advisor_email,
        ),
        config=EmailGenerationConfig(fallback_templates=FALLBACK_TEMPLATES),
        nvidia_client=llm_client,
    )

    all_messages = []
    print(
        f"Generating {args.conversations} synthetic conversation threads concurrently..."
    )

    # Schedule LLM or template generations concurrently
    tasks = []
    for idx in range(args.conversations):
        topic = random.choice(topics)
        thread_length = random.randint(5, 20)
        thread_format = args.thread_format

        # Select client from the pool using round-robin index
        client = client_pool.get_client(idx)

        print(
            f" - Scheduling Thread {idx + 1}: "
            f"Topics='{topic}', "
            f"Client='{client.name}' ({client.email}), "
            f"Format='{thread_format}'"
        )

        tasks.append(
            generator.generate_thread(
                topic=topic,
                client=client,
                thread_length=thread_length,
                thread_format=thread_format,
            )
        )

    results = await asyncio.gather(*tasks)
    for messages in results:
        all_messages.extend(messages)

    response_wrapper = {"value": all_messages}

    # Ensure parent output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with Path.open(output_path, "w") as f:
        json.dump(response_wrapper, f, indent=2)

    print(
        f"\nSuccessfully generated {len(all_messages)} \
            total messages across {args.conversations} threads."
    )
    print(f"Saved dataset to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
