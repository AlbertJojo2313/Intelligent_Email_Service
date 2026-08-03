from datetime import datetime
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any

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
    attachments_summary: list[dict[str, Any]] = field(default_factory=list)
    estimated_tokens: int = 0
    used_llmlingua: bool = False
    compressed_messages: list[dict[str, Any]] = field(default_factory=list)


class EmailCompressor:
    """
    Context compressor for email threads of any shape.

    Handling rules:
      - FULL_QUOTED: Takes the latest message (which contains the embedded quoted history),
        compresses its body, and returns it as the single `compressed_body`.
      - MODIFIED: Combines all chronological messages into a unified thread text,
        then compresses that combined text into a single `compressed_body`.
    """

    # Cache of loaded LLMLingua models, keyed by model name
    _llm_compressors: dict[str, Any] = {}

    def __init__(self, config: CompressorConfig | None = None):
        self.config = config or CompressorConfig()
        self.use_llmlingua = self.config.use_llmlingua and HAS_LLMLINGUA

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
                compressed_messages=[],
                attachments_summary=[],
                estimated_tokens=0,
                used_llmlingua=False,
            )

        attachments = []
        for msg in messages:
            attachments.extend(self._extract_attachments(msg))

        used_lingua = False
        processed_msgs = []

        if fmt == "full_quoted" or len(messages) == 1:
            latest_msg = messages[-1]
            text = self._extract_body(latest_msg)
            needs_comp = len(text) > self.config.max_full_body_chars

            if needs_comp and self.use_llmlingua:
                compressed_body = self._compress_llmlingua(text)
                used_lingua = compressed_body != text
            elif needs_comp:
                compressed_body = self._truncate_text(text)
            else:
                compressed_body = text

            formatted = self._format_message(latest_msg, is_historical=False, body=compressed_body)
            processed_msgs.append(formatted)

        else:
            chrono_texts = []
            cutoff = max(len(messages) - self.config.recent_full_count, 0)

            for idx, msg in enumerate(messages):
                text = self._extract_body(msg)
                is_historical = idx < cutoff
                needs_comp = is_historical or len(text) > self.config.max_full_body_chars

                if needs_comp and self.use_llmlingua:
                    c_body = self._compress_llmlingua(text)
                    used_lingua = used_lingua or (c_body != text)
                elif needs_comp:
                    c_body = self._truncate_text(text)
                else:
                    c_body = text

                formatted = self._format_message(msg, is_historical=is_historical, body=c_body)
                processed_msgs.append(formatted)

                sender = getattr(msg, "sender", None) if hasattr(msg, "sender") else None
                if not sender and isinstance(msg, dict):
                    sender_obj = msg.get("from") or {}
                    if isinstance(sender_obj, dict):
                        addr_info = sender_obj.get("emailAddress") or {}
                        if isinstance(addr_info, dict):
                            sender = addr_info.get("name") or addr_info.get("address") or ""

                header = f"[{sender}] " if sender else ""
                chrono_texts.append(f"{header}{c_body}")

            combined_raw = "\n\n---\n\n".join(chrono_texts)
            needs_comp = len(combined_raw) > self.config.max_full_body_chars

            if needs_comp and self.use_llmlingua:
                compressed_body = self._compress_llmlingua(combined_raw)
                used_lingua = used_lingua or (compressed_body != combined_raw)
            elif needs_comp:
                compressed_body = self._truncate_text(combined_raw)
            else:
                compressed_body = combined_raw

        tokens = math.ceil(len(compressed_body) / AVG_CHARS_PER_TOKEN) if compressed_body else 0

        return CompressedThread(
            subject=subject,
            conversation_id=conversation_id,
            format=fmt,
            total_messages=len(messages),
            compressed_body=compressed_body,
            compressed_messages=processed_msgs,
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
        except Exception as err:
            logger.warning("LLMLingua compression failed, falling back to truncation: %s", err)
        return self._truncate_text(text)

    def _truncate_text(self, text: str) -> str:
        if len(text) <= self.config.max_full_body_chars:
            return text
        return text[: self.config.max_full_body_chars].rstrip() + " [... truncated]"

    def _format_message(
        self, msg: Any, is_historical: bool, body: str
    ) -> dict[str, Any]:
        if hasattr(msg, "__dict__"):
            compressed_msg = {
                k: v.isoformat() if isinstance(v, datetime) else v
                for k, v in msg.__dict__.items()
            }
        elif isinstance(msg, dict):
            compressed_msg = {
                k: v.isoformat() if isinstance(v, datetime) else v
                for k, v in msg.items()
            }
        else:
            compressed_msg = {}

        compressed_msg["compressed_body"] = body
        compressed_msg["is_historical"] = is_historical
        compressed_msg["attachments"] = self._extract_attachments(msg)
        compressed_msg["estimated_tokens"] = math.ceil(len(body) / AVG_CHARS_PER_TOKEN) if body else 0
        return compressed_msg

    def _extract_attachments(self, msg: Any) -> list[dict[str, Any]]:
        if hasattr(msg, "attachments"):
            raw = getattr(msg, "attachments", []) or []
        elif isinstance(msg, dict):
            raw = msg.get("attachments") or []
        else:
            raw = []

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
    def _extract_body(msg: Any) -> str:
        if hasattr(msg, "cleaned_body") and getattr(msg, "cleaned_body"):
            return str(getattr(msg, "cleaned_body"))
        if hasattr(msg, "body_content") and getattr(msg, "body_content"):
            return str(getattr(msg, "body_content"))
        if isinstance(msg, dict):
            cleaned = msg.get("cleaned_body")
            if isinstance(cleaned, str) and cleaned:
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
