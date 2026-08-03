import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Optional LLMLingua import with fallback
try:
    from llmlingua import PromptCompressor  # type: ignore

    HAS_LLMLINGUA = True
except ImportError:
    PromptCompressor = None
    HAS_LLMLINGUA = False


from ..config import CompressorConfig

AVG_CHARS_PER_TOKEN: float = 4.0


@dataclass
class CompressedThread:
    """Compressed email thread output for LLM context windows."""

    subject: str
    conversation_id: str | None
    format: str
    total_messages: int
    compressed_body: str
    sender: str | None = None
    senders: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    attachments_summary: list[dict[str, Any]] = field(default_factory=list)
    estimated_tokens: int = 0
    used_llmlingua: bool = False


class EmailCompressor:
    """
    Context compressor for email threads of any shape.

    Handling rules:
      - FULL_QUOTED (or any single-message thread): compress the one message's
        body directly.
      - MODIFIED: compress/truncate any individual messages that need it,
        join everything into one chronological text, then compress that
        combined text again if it's still too large.

    New thread formats can be supported by adding an entry to `_strategies`
    rather than editing `compress_processed_thread` itself.
    """

    # Cache of loaded LLMLingua models, keyed by model name
    _llm_compressors: dict[str, Any] = {}

    def __init__(self, config: CompressorConfig | None = None):
        self.config = config or CompressorConfig()
        self.use_llmlingua = self.config.use_llmlingua and HAS_LLMLINGUA
        self._strategies: dict[
            str, Callable[[list[dict[str, Any]]], tuple[str, bool]]
        ] = {
            "full_quoted": self._compress_full_quoted,
        }

    def compress_processed_thread(self, thread: Any) -> CompressedThread:
        """Compresses a ProcessedThread instance into a unified CompressedThread."""
        messages = getattr(thread, "messages", []) or []
        conversation_id = getattr(thread, "conversation_id", None)
        subject = self.clean_subject(getattr(thread, "subject", ""))
        fmt = str(getattr(thread, "format", "modified")).lower()

        if not messages:
            return CompressedThread(
                subject=subject,
                conversation_id=conversation_id,
                format=fmt,
                total_messages=0,
                compressed_body="",
            )

        normalized = [self._normalize_message(m) for m in messages]

        attachments: list[dict[str, Any]] = []
        senders_seen: dict[str, None] = {}
        participants: set[str] = set()

        for nm in normalized:
            attachments.extend(nm["attachments"])
            if nm["sender"]:
                senders_seen.setdefault(nm["sender"], None)
                participants.add(nm["sender"])
            participants.update(nm["recipients"])

        senders_list = list(senders_seen)
        latest_sender = senders_list[-1] if senders_list else None

        # A lone message is always handled like a full_quoted thread,
        # regardless of the reported format.
        strategy = (
            self._compress_full_quoted
            if len(normalized) == 1
            else self._strategies.get(fmt, self._compress_modified)
        )
        compressed_body, used_lingua = strategy(normalized)

        tokens = (
            math.ceil(len(compressed_body) / AVG_CHARS_PER_TOKEN)
            if compressed_body
            else 0
        )

        return CompressedThread(
            subject=subject,
            conversation_id=conversation_id,
            format=fmt,
            total_messages=len(messages),
            compressed_body=compressed_body,
            sender=latest_sender,
            senders=senders_list,
            participants=sorted(participants),
            attachments_summary=attachments,
            estimated_tokens=tokens,
            used_llmlingua=used_lingua,
        )

    # ---- Format strategies -------------------------------------------------

    def _compress_full_quoted(self, normalized: list[dict[str, Any]]) -> tuple[str, bool]:
        """The latest message already contains the full embedded quoted history."""
        text = normalized[-1]["body"]
        return self._compress_if_needed(text)

    def _compress_modified(self, normalized: list[dict[str, Any]]) -> tuple[str, bool]:
        """Compresses old messages individually, then compresses the joined result."""
        cutoff = max(len(normalized) - self.config.recent_full_count, 0)
        used_lingua = False
        chrono_texts = []

        for idx, nm in enumerate(normalized):
            body, used = self._compress_if_needed(nm["body"], force=idx < cutoff)
            used_lingua = used_lingua or used
            header = f"[{nm['sender']}] " if nm["sender"] else ""
            chrono_texts.append(f"{header}{body}")

        combined = "\n\n---\n\n".join(chrono_texts)
        compressed_body, used = self._compress_if_needed(combined)
        return compressed_body, used_lingua or used

    # ---- Compression core ---------------------------------------------------

    def _compress_if_needed(self, text: str, force: bool = False) -> tuple[str, bool]:
        """
        Single point of truth for "does this text need compressing, and if
        so, how." Replaces what used to be three duplicated
        if/elif/else blocks. Returns (body, used_llmlingua).
        """
        if not force and len(text) <= self.config.max_full_body_chars:
            return text, False

        if self.use_llmlingua:
            compressed, used = self._compress_llmlingua(text)
            if used:
                return compressed, True

        return self._truncate_text(text), False

    def _compress_llmlingua(self, text: str) -> tuple[str, bool]:
        """Attempts LLMLingua compression. Returns (text, success) — success
        is explicit rather than inferred from string inequality, so a
        fallback-to-truncation result is never mistaken for a real
        LLMLingua compression."""
        if not text or len(text) < self.config.activate_compressor_message_length:
            return text, False
        try:
            model = self._get_llmlingua_model()
            if model:
                res = model.compress_prompt(
                    context=[text],
                    rate=self.config.llmlingua_rate,
                    use_sentence_level_filter=False,
                    token_budget_ratio=self.config.token_budget_ratio,
                    keep_first_sentence=self.config.keep_first_sentence,
                    force_tokens=self.config.force_tokens,
                )
                compressed = res.get("compressed_prompt")
                if compressed:
                    return compressed, True
        except Exception as err:
            logger.warning(
                "LLMLingua compression failed, falling back to truncation: %s", err
            )
        return text, False

    def _truncate_text(self, text: str) -> str:
        if len(text) <= self.config.max_full_body_chars:
            return text
        return text[: self.config.max_full_body_chars].rstrip() + " [... truncated]"

    # ---- Message normalization (Adapter) ------------------------------------

    @staticmethod
    def _normalize_message(msg: Any) -> dict[str, Any]:
        """
        Adapts either an attribute-based message object or a raw dict (e.g.
        Graph API shape) into one canonical dict, so every downstream piece
        of logic reads a single shape instead of re-checking "is this a
        dict or an object?" on every field access.
        """
        if isinstance(msg, dict):
            sender = EmailCompressor._sender_from_dict(msg)
            recipients = EmailCompressor._recipients_from_dict(msg)
            body = EmailCompressor._body_from_dict(msg)
            attachments = msg.get("attachments") or []
        else:
            sender = str(getattr(msg, "sender", "") or "")
            recipients = [str(r) for r in (getattr(msg, "recipients", None) or []) if r]
            body = str(
                getattr(msg, "cleaned_body", "") or getattr(msg, "body_content", "") or ""
            )
            attachments = getattr(msg, "attachments", None) or []

        return {
            "sender": sender,
            "recipients": recipients,
            "body": body,
            "attachments": EmailCompressor._clean_attachments(attachments),
        }

    @staticmethod
    def _sender_from_dict(msg: dict[str, Any]) -> str:
        sender_obj = msg.get("from") or {}
        if isinstance(sender_obj, str):
            return sender_obj
        if isinstance(sender_obj, dict):
            addr_info = sender_obj.get("emailAddress") or {}
            if isinstance(addr_info, dict):
                return addr_info.get("address") or addr_info.get("name") or ""
        return ""

    @staticmethod
    def _recipients_from_dict(msg: dict[str, Any]) -> list[str]:
        recipients = []
        for r in msg.get("toRecipients") or []:
            if not isinstance(r, dict):
                continue
            addr_info = r.get("emailAddress") or {}
            if not isinstance(addr_info, dict):
                continue
            addr = addr_info.get("address") or addr_info.get("name")
            if addr:
                recipients.append(addr)
        return recipients

    @staticmethod
    def _body_from_dict(msg: dict[str, Any]) -> str:
        cleaned = msg.get("cleaned_body")
        if isinstance(cleaned, str) and cleaned:
            return cleaned
        body_obj = msg.get("body")
        if isinstance(body_obj, dict):
            return str(body_obj.get("content") or "")
        if isinstance(body_obj, str):
            return body_obj
        return ""

    @staticmethod
    def _clean_attachments(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        return [
            {
                "id": a.get("id"),
                "name": a.get("name") or a.get("fileName") or "attachment",
                "contentType": a.get("contentType")
                or a.get("content_type")
                or "application/octet-stream",
                "size": a.get("size") or 0,
            }
            for a in raw
            if isinstance(a, dict)
        ]

    def _get_llmlingua_model(self) -> Any:
        """Loads (and caches, per model name) the LLMLingua compressor for this instance's model."""
        if not HAS_LLMLINGUA:
            return None
        model_name = self.config.llmlingua_model
        if model_name not in self._llm_compressors:
            self._llm_compressors[model_name] = PromptCompressor(
                model_name=model_name,
                use_llmlingua2=True,
                device_map=self.config.llmlingua_device,
            )  # pyright: ignore[reportOptionalCall]
        return self._llm_compressors[model_name]

    @staticmethod
    def clean_subject(subject: str) -> str:
        return re.sub(
            r"^(?:\s*(?:re|fwd|fw):\s*)+", "", subject, flags=re.IGNORECASE
        ).strip()
