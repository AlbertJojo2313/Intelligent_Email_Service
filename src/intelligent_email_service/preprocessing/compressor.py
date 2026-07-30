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
    Streamlined Context Compressor for Email Threads.

    - FULL_QUOTED threads (1 message): Bypasses LLMLingua, returning cleaned text directly.
    - MODIFIED threads (multi-message): Keeps newest K messages full-text and applies LLMLingua
      or heuristic truncation to older historical messages.
    """

    _llm_compressor: Any = None

    def __init__(
        self,
        recent_full_count: int = 2,
        max_older_chars: int = 300,
        use_llmlingua: bool = True,
        llmlingua_rate: float = 0.5,
        llmlingua_model: str = "microsoft/llmlingua-2-bert-base-multilingual-cased-meeting",
    ):
        self.recent_full_count = max(1, recent_full_count)
        self.max_older_chars = max_older_chars
        self.use_llmlingua = use_llmlingua and HAS_LLMLINGUA
        self.llmlingua_rate = llmlingua_rate
        self.llmlingua_model = llmlingua_model

    def compress_processed_thread(self, thread: Any) -> CompressedThread:
        """Compresses a ProcessedThread instance."""
        messages = getattr(thread, "messages", []) or []
        thread_format = getattr(thread, "format", "full_quoted")
        conversation_id = getattr(thread, "conversation_id", None)
        subject = self.clean_subject(getattr(thread, "subject", ""))

        # FULL_QUOTED or short threads: No compression needed, return cleaned messages directly
        if str(thread_format) == "full_quoted" or len(messages) <= self.recent_full_count:
            return self._build_uncompressed_payload(messages, subject, conversation_id)

        # MODIFIED multi-message threads: Compress older historical messages
        return self._compress_multi_message_thread(messages, subject, conversation_id)

    def _build_uncompressed_payload(
        self, messages: list[dict[str, Any]], subject: str, conversation_id: str | None
    ) -> CompressedThread:
        processed = []
        attachments = []
        for msg in messages:
            cleaned = self._format_message(msg, is_historical=False)
            processed.append(cleaned)
            attachments.extend(cleaned["attachments"])

        tokens = sum(m["estimated_tokens"] for m in processed)
        return CompressedThread(
            subject=subject,
            conversation_id=conversation_id,
            total_messages=len(messages),
            compressed_messages=processed,
            attachments_summary=attachments,
            estimated_tokens=tokens,
            used_llmlingua=False,
        )

    def _compress_multi_message_thread(
        self, messages: list[dict[str, Any]], subject: str, conversation_id: str | None
    ) -> CompressedThread:
        cutoff = len(messages) - self.recent_full_count
        processed = []
        attachments = []
        used_lingua = False

        for idx, msg in enumerate(messages):
            is_historical = idx < cutoff
            if is_historical and self.use_llmlingua:
                compressed_body = self._compress_llmlingua(msg)
                used_lingua = True
            elif is_historical:
                compressed_body = self._truncate_text(msg)
            else:
                compressed_body = self._extract_body(msg)

            formatted = self._format_message(
                msg, is_historical=is_historical, body=compressed_body
            )
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

    def _compress_llmlingua(self, msg: dict[str, Any]) -> str:
        text = self._extract_body(msg)
        if not text or len(text) < 100:
            return text
        try:
            model = self._get_llmlingua_model()
            if model:
                res = model.compress_prompt(context=[text], rate=self.llmlingua_rate)
                return res.get("compressed_prompt") or text
        except Exception:
            pass
        return self._truncate_text(msg)

    def _truncate_text(self, msg: dict[str, Any]) -> str:
        text = self._extract_body(msg)
        if len(text) <= self.max_older_chars:
            return text
        return text[: self.max_older_chars].rstrip() + " [... truncated]"

    def _format_message(
        self, msg: dict[str, Any], is_historical: bool, body: str | None = None
    ) -> dict[str, Any]:
        compressed_msg = dict(msg)
        final_body = body if body is not None else self._extract_body(msg)
        compressed_msg["compressed_body"] = final_body
        compressed_msg["is_historical"] = is_historical
        compressed_msg["attachments"] = self._extract_attachments(msg)
        compressed_msg["estimated_tokens"] = math.ceil(len(final_body) / 4.0) if final_body else 0
        return compressed_msg

    def _extract_attachments(self, msg: dict[str, Any]) -> list[dict[str, Any]]:
        raw = msg.get("attachments") or []
        if not isinstance(raw, list):
            return []
        return [
            {
                "id": a.get("id"),
                "name": a.get("name") or a.get("fileName") or "attachment",
                "contentType": a.get("contentType") or a.get("content_type") or "application/octet-stream",
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
        elif isinstance(body_obj, str):
            return body_obj
        return ""

    @classmethod
    def _get_llmlingua_model(cls) -> Any:
        if HAS_LLMLINGUA and cls._llm_compressor is None:
            cls._llm_compressor = PromptCompressor(
                model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meeting",
                use_llmlingua2=True,
            )
        return cls._llm_compressor

    @staticmethod
    def clean_subject(subject: str) -> str:
        return re.sub(r"^(?:\s*(?:re|fwd|fw):\s*)+", "", subject, flags=re.IGNORECASE).strip()
