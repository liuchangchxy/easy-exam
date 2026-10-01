"""Contextual AI Tutor and SSE streaming service.

Assembles question metadata (stem, options, user wrong choice, correct answer,
explanation, mistake cause) into structured system prompts, supports OpenAI/Ollama
compatible SSE streaming, and provides a graceful offline fallback when no LLM is configured.
"""
from __future__ import annotations

import json
import os
from typing import Any, Generator, Optional
import urllib.error
import urllib.request

OFFLINE_FALLBACK_MESSAGE = (
    "💡 提示：当前未检测到可用的大模型服务或网络离线。您可以在设置中配置本地 Ollama "
    "(如 http://localhost:11434/v1) 或云端 API Key 开启 AI 智能助教辅导。"
)

DEFAULT_SYSTEM_PERSONA = (
    "你是一位专业、耐心且富有启发性的AI题境助教。你的任务是针对学生在刷题过程中遇到的错题进行针对性辅导与思维点拨。\n"
    "请根据以下题目上下文，深入剖析学生作答出现偏差的根本原因，分析干扰项的迷惑之处，阐明正确答案的解题思路与核心知识点，并引导学生举一反三。"
)

DEFAULT_SYSTEM_PERSONA_EN = (
    "You are a professional, patient, and analytical AI Exam Tutor. "
    "Your mission is to guide the student through question analysis, dissecting misconceptions, "
    "explaining why distractors are incorrect, and elucidating the solution path and core principles in clear English."
)


def _format_options(options: Any) -> str:
    """Format question options into a neat string representation."""
    if not options:
        return "无"
    if isinstance(options, str):
        return options.strip() or "无"
    if isinstance(options, list):
        lines = []
        for item in options:
            if isinstance(item, dict):
                k = str(item.get("key") or "").strip()
                c = str(item.get("content") or "").strip()
                if k and c:
                    lines.append(f"{k}. {c}")
                elif k:
                    lines.append(k)
                elif c:
                    lines.append(c)
            elif isinstance(item, str):
                lines.append(item.strip())
            else:
                lines.append(str(item))
        return "\n".join(lines) if lines else "无"
    return str(options)


def build_tutor_prompt(
    question_context: dict[str, Any],
    user_query: Optional[str] = None,
    history: Optional[list[dict[str, str]]] = None,
    target_lang: str = "zh-CN",
) -> list[dict[str, str]]:
    """Build OpenAI/Ollama compatible message list injected with full question context.

    Schema of question_context:
        stem: str
        options: list[dict] e.g. [{"key": "A", "content": "..."}]
        user_answer: str
        correct_answer: str
        explanation: str
        mistake_cause: str e.g. "CONCEPT_GAP", "OPTION_TRAP", etc.
    """
    stem = str(question_context.get("stem") or "").strip()
    opts_str = _format_options(question_context.get("options"))
    user_answer = str(question_context.get("user_answer") or "").strip() or "未作答"
    correct_answer = str(question_context.get("correct_answer") or "").strip() or "无"
    explanation = str(question_context.get("explanation") or "").strip() or "暂无解析"
    mistake_cause = str(question_context.get("mistake_cause") or "").strip() or "未标记"

    is_english = bool(target_lang and str(target_lang).lower().startswith("en"))

    if is_english:
        system_content = (
            f"{DEFAULT_SYSTEM_PERSONA_EN}\n\n"
            f"【Question Stem】\n{stem}\n\n"
            f"【Options】\n{opts_str}\n\n"
            f"【User Answer】\n{user_answer}\n\n"
            f"【Standard Answer】\n{correct_answer}\n\n"
            f"【Official Explanation】\n{explanation}\n\n"
            f"【Mistake Category】\n{mistake_cause}\n\n"
            f"【Tutoring Directives】\n"
            f"1. Pinpoint the student's core misconception in English;\n"
            f"2. Detail why distractors are invalid;\n"
            f"3. Explain the rigorous solution process and underlying concepts;\n"
            f"4. Provide actionable exam-taking techniques for similar problems."
        )
    else:
        system_content = (
            f"{DEFAULT_SYSTEM_PERSONA}\n\n"
            f"【题干】\n{stem}\n\n"
            f"【选项】\n{opts_str}\n\n"
            f"【用户作答】\n{user_answer}\n\n"
            f"【正确答案】\n{correct_answer}\n\n"
            f"【题目解析】\n{explanation}\n\n"
            f"【用户错因标签】\n{mistake_cause}\n\n"
            f"【辅导要求】\n"
            f"1. 精准定位学生的薄弱环节与思维偏差；\n"
            f"2. 详细剖析干扰项的逻辑陷阱；\n"
            f"3. 讲解正确答案的严密推导过程与关键考点；\n"
            f"4. 条理清晰、亲切鼓舞，给出同类题目的避坑解题方法。"
        )

    messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]

    if history:
        for h in history:
            if isinstance(h, dict) and "role" in h and "content" in h:
                messages.append({"role": str(h["role"]), "content": str(h["content"])})

    if user_query and user_query.strip():
        final_query = user_query.strip()
    elif is_english:
        final_query = "Please analyze my error and explain the key concepts."
    else:
        final_query = "请分析我选错的原因，并给出解题关键点"

    messages.append({"role": "user", "content": final_query})

    return messages


class AIService:
    """AI Tutor service connecting to OpenAI/Ollama compatible endpoints with SSE streaming and offline fallback."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.api_key = (
            api_key if api_key is not None else os.environ.get("LLM_API_KEY", "")
        )
        self.base_url = (
            base_url
            if base_url is not None
            else os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
        )
        self.model = (
            model if model is not None else os.environ.get("LLM_MODEL", "qwen2.5:7b")
        )
        self.timeout = timeout

    def is_configured(self) -> bool:
        """Check whether LLM service endpoint or API key is configured."""
        has_key = bool(self.api_key and self.api_key.strip())
        has_url = bool(self.base_url and self.base_url.strip())
        return has_key or has_url

    def _get_endpoint(self) -> str:
        """Construct full chat completions endpoint URL."""
        base = self.base_url.strip().rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def _build_headers(self, is_stream: bool = False) -> dict[str, str]:
        """Build HTTP headers for request."""
        headers = {
            "Content-Type": "application/json",
        }
        if is_stream:
            headers["Accept"] = "text/event-stream"
        if self.api_key and self.api_key.strip():
            headers["Authorization"] = f"Bearer {self.api_key.strip()}"
        return headers

    def stream_chat(
        self, messages: list[dict[str, str]]
    ) -> Generator[str, None, None]:
        """Stream chat completions using SSE protocol.

        Yields text chunks as they arrive. If connection fails or LLM is unconfigured,
        catches exceptions gracefully and yields friendly offline fallback message.
        """
        if not self.is_configured():
            yield OFFLINE_FALLBACK_MESSAGE
            return

        endpoint = self._get_endpoint()
        headers = self._build_headers(is_stream=True)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }

        try:
            req = urllib.request.Request(
                url=endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
        except Exception:
            yield OFFLINE_FALLBACK_MESSAGE
            return

        has_yielded = False
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for raw_line in resp:
                    if isinstance(raw_line, bytes):
                        line = raw_line.decode("utf-8", errors="replace").strip()
                    else:
                        line = str(raw_line).strip()
                    if not line:
                        continue
                    if line.startswith("data:"):
                        data_part = line[len("data:") :].strip()
                        if data_part == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_part)
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content")
                                if content:
                                    has_yielded = True
                                    yield content
                        except json.JSONDecodeError:
                            continue
                    elif line.startswith("{"):
                        # Non-SSE JSON fallback
                        try:
                            chunk = json.loads(line)
                            choices = chunk.get("choices", [])
                            if choices:
                                content = choices[0].get("message", {}).get("content")
                                if content:
                                    has_yielded = True
                                    yield content
                                    break
                        except json.JSONDecodeError:
                            pass
        except Exception:
            if not has_yielded:
                yield OFFLINE_FALLBACK_MESSAGE
            return

        if not has_yielded:
            yield OFFLINE_FALLBACK_MESSAGE

    def chat_complete(self, messages: list[dict[str, str]]) -> str:
        """Non-streaming version of chat completions returning complete response text."""
        if not self.is_configured():
            return OFFLINE_FALLBACK_MESSAGE

        endpoint = self._get_endpoint()
        headers = self._build_headers(is_stream=False)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        try:
            req = urllib.request.Request(
                url=endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw_body = resp.read()
                if isinstance(raw_body, bytes):
                    body = raw_body.decode("utf-8", errors="replace").strip()
                else:
                    body = str(raw_body).strip()

                if body.startswith("data:"):
                    chunks: list[str] = []
                    for line in body.splitlines():
                        line = line.strip()
                        if line.startswith("data:"):
                            part = line[len("data:") :].strip()
                            if part == "[DONE]":
                                break
                            try:
                                c = json.loads(part)
                                choices = c.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    msg_obj = choices[0].get("message", {})
                                    text = delta.get("content") or msg_obj.get(
                                        "content"
                                    )
                                    if text:
                                        chunks.append(text)
                            except json.JSONDecodeError:
                                continue
                    if chunks:
                        return "".join(chunks)

                data = json.loads(body)
                choices = data.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    content = msg.get("content")
                    if content is not None:
                        return content
                return OFFLINE_FALLBACK_MESSAGE
        except Exception:
            return OFFLINE_FALLBACK_MESSAGE
