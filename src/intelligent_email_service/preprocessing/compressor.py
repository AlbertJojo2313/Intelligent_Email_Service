import math
import re
from dataclasses import dataclass, field
from typing import Any

# Optional LLMLingua import with fallback
try:
    from llmlingua import PromptCompressor  # type: ignore

    HAS_LLMLINGUA = True
except ImportError:
    PromptCompressor = None
    HAS_LLMLINGUA = False


from ..config import CompressorConfig

# Average character count per estimated LLM token
AVG_CHARS_PER_TOKEN: float = 4.0


@dataclass
class CompressedThread:
    """Compressed email thread output for LLM context windows."""

    subject: str
    conversation_id: str | None
    total_messages: int
    compressed_messages: list[dict[str, Any]]
    attachments_summary: list[dict[str, Any]] = field(default_factory=list)
    estimated_tokens: int = 0
    used_llmlingua: bool = False


class EmailCompressor:
    """
    Context compressor for email threads of any shape.

    Every message is compressed the same way: the newest `recent_full_count`
    messages are kept full-text *unless* they exceed `max_full_body_chars`,
    in which case they're compressed too (via LLMLingua, falling back to
    truncation). Older messages are always compressed. This means a
    single-message "full_quoted" thread that embeds a huge quoted history
    is no longer exempt just because it's one message.
    """

    # Cache of loaded LLMLingua models, keyed by model name, shared across
    # instances so repeated construction doesn't reload the model, without
    # differently-configured instances clobbering each other's model.
    _llm_compressors: dict[str, Any] = {}

    def __init__(self, config: CompressorConfig | None = None):
        self.config = config or CompressorConfig()
        # Override use_llmlingua with HAS_LLMLINGUA availability
        self.use_llmlingua = self.config.use_llmlingua and HAS_LLMLINGUA

    def compress_processed_thread(self, thread: Any) -> CompressedThread:
        """Compresses a ProcessedThread instance, regardless of its format."""
        messages = getattr(thread, "messages", []) or []
        conversation_id = getattr(thread, "conversation_id", None)
        subject = self.clean_subject(getattr(thread, "subject", ""))
        cutoff = max(len(messages) - self.config.recent_full_count, 0)

        processed = []
        attachments = []
        used_lingua = False

        for idx, msg in enumerate(messages):
            text = self._extract_body(msg)
            is_historical = idx < cutoff
            needs_compression = (
                is_historical or len(text) > self.config.max_full_body_chars
            )

            if needs_compression and self.use_llmlingua:
                body = self._compress_llmlingua(text)
                used_lingua = used_lingua or body != text
            elif needs_compression:
                body = self._truncate_text(text)
            else:
                body = text

            formatted = self._format_message(msg, is_historical=is_historical, body=body)
            processed.append(formatted)
            attachments.extend(formatted["attachments"])

        tokens = sum(m["estimated_tokens"] for m in processed)
        return CompressedThread(
            subject=subject,
            conversation_id=conversation_id,
            total_messages=len(messages),
            compressed_messages=processed,
            attachments_summary=attachments,
            estimated_tokens=tokens,
            used_llmlingua=used_lingua,
        )

    def _compress_llmlingua(self, text: str) -> str:
        if not text or len(text) < self.config.activate_compressor_message_length:
            return text
        try:
            model = self._get_llmlingua_model()
            if model:
                res = model.compress_prompt(
                    context=[text], rate=self.config.llmlingua_rate
                )
                return res.get("compressed_prompt") or text
        except Exception:
            # Model failure shouldn't take down the whole thread compression;
            # fall back to plain truncation instead.
            pass
        return self._truncate_text(text)

    def _truncate_text(self, text: str) -> str:
        if len(text) <= self.config.max_full_body_chars:
            return text
        return text[: self.config.max_full_body_chars].rstrip() + " [... truncated]"

    def _format_message(
        self, msg: dict[str, Any], is_historical: bool, body: str
    ) -> dict[str, Any]:
        compressed_msg = dict(msg)
        compressed_msg["compressed_body"] = body
        compressed_msg["is_historical"] = is_historical
        compressed_msg["attachments"] = self._extract_attachments(msg)
        compressed_msg["estimated_tokens"] = (
            math.ceil(len(body) / AVG_CHARS_PER_TOKEN) if body else 0
        )
        return compressed_msg

    def _extract_attachments(self, msg: dict[str, Any]) -> list[dict[str, Any]]:
        raw = msg.get("attachments") or []
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

    @staticmethod
    def _extract_body(msg: dict[str, Any]) -> str:
        cleaned = msg.get("cleaned_body")
        if isinstance(cleaned, str):
            return cleaned
        body_obj = msg.get("body")
        if isinstance(body_obj, dict):
            return str(body_obj.get("content") or "")
        if isinstance(body_obj, str):
            return body_obj
        return ""

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
