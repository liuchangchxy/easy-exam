"""Tests for contextual AI tutor and streaming service."""
import io
import json
import os
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from backend.services.ai_service import (
    AIService,
    build_tutor_prompt,
    OFFLINE_FALLBACK_MESSAGE,
)


class TestAIService(unittest.TestCase):
    """Test suite for AI tutor prompt builder and SSE streaming service."""

    def setUp(self):
        self.sample_context = {
            "stem": "关于 Python GIL 的描述，下列哪项是正确的？",
            "options": [
                {"key": "A", "content": "GIL 提升了多线程 CPU 密集型任务的性能"},
                {"key": "B", "content": "GIL 确保了同一时刻只有一个线程执行 Python 字节码"},
                {"key": "C", "content": "GIL 仅在 Jython 中存在"},
                {"key": "D", "content": "GIL 使得多进程无法并行"},
            ],
            "user_answer": "A",
            "correct_answer": "B",
            "explanation": "GIL（全局解释器锁）是 CPython 的特性，同一时刻只允许一个线程执行字节码。",
            "mistake_cause": "CONCEPT_GAP",
        }

    def test_build_tutor_prompt_context_injection(self):
        """Prompt should contain stem, options, user_answer, correct_answer, explanation, and mistake_cause."""
        messages = build_tutor_prompt(self.sample_context)
        self.assertIsInstance(messages, list)
        self.assertGreaterEqual(len(messages), 2)

        # Check system message
        system_msg = messages[0]
        self.assertEqual(system_msg["role"], "system")
        content = system_msg["content"]

        self.assertIn("【题干】", content)
        self.assertIn("关于 Python GIL 的描述", content)
        self.assertIn("【选项】", content)
        self.assertIn("A. GIL 提升了多线程 CPU 密集型任务的性能", content)
        self.assertIn("B. GIL 确保了同一时刻只有一个线程执行 Python 字节码", content)
        self.assertIn("【用户作答】", content)
        self.assertIn("A", content)
        self.assertIn("【正确答案】", content)
        self.assertIn("B", content)
        self.assertIn("【题目解析】", content)
        self.assertIn("GIL（全局解释器锁）是 CPython 的特性", content)
        self.assertIn("【用户错因标签】", content)
        self.assertIn("CONCEPT_GAP", content)

        # Check default user message
        user_msg = messages[-1]
        self.assertEqual(user_msg["role"], "user")
        self.assertEqual(user_msg["content"], "请分析我选错的原因，并给出解题关键点")

    def test_build_tutor_prompt_multilingual_english(self):
        """Prompt should switch persona, headers, and default query to English when target_lang starts with 'en'."""
        messages = build_tutor_prompt(self.sample_context, target_lang="en-US")
        sys_msg = messages[0]["content"]
        self.assertIn("AI Exam Tutor", sys_msg)
        self.assertIn("【Question Stem】", sys_msg)
        self.assertIn("【Standard Answer】", sys_msg)
        self.assertIn("【Tutoring Directives】", sys_msg)
        user_msg = messages[-1]["content"]
        self.assertIn("analyze my error", user_msg)

    def test_build_tutor_prompt_custom_query(self):
        """Custom user_query should override default user message."""
        messages = build_tutor_prompt(
            self.sample_context,
            user_query="请问选项 C 为什么是错的？"
        )
        self.assertEqual(messages[-1]["role"], "user")
        self.assertEqual(messages[-1]["content"], "请问选项 C 为什么是错的？")

    def test_build_tutor_prompt_multi_turn_history(self):
        """Conversation history should be preserved between system prompt and user message."""
        history = [
            {"role": "user", "content": "这道题为什么不选A？"},
            {"role": "assistant", "content": "因为 A 选项把 GIL 的作用理解反了，GIL 反而限制了多线程并发计算。"},
        ]
        messages = build_tutor_prompt(
            self.sample_context,
            user_query="那我应该怎么实现真正的多核并行？",
            history=history,
        )
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1], history[0])
        self.assertEqual(messages[2], history[1])
        self.assertEqual(messages[3]["role"], "user")
        self.assertEqual(messages[3]["content"], "那我应该怎么实现真正的多核并行？")

    def test_build_tutor_prompt_empty_or_missing_fields(self):
        """Prompt builder should handle empty or missing context fields gracefully."""
        sparse_context = {
            "stem": "简答题：什么是死锁？",
        }
        messages = build_tutor_prompt(sparse_context)
        self.assertEqual(messages[0]["role"], "system")
        content = messages[0]["content"]
        self.assertIn("简答题：什么是死锁？", content)
        self.assertIn("【用户作答】", content)
        self.assertIn("【用户错因标签】", content)

    def test_ai_service_defaults_and_env(self):
        """AIService should default to Ollama fnOS settings and respect env vars."""
        with patch.dict(os.environ, {}, clear=True):
            service = AIService()
            self.assertEqual(service.base_url, "http://localhost:11434/v1")
            self.assertEqual(service.model, "qwen2.5:7b")
            self.assertEqual(service.api_key, "")
            self.assertTrue(service.is_configured())

        with patch.dict(
            os.environ,
            {
                "LLM_API_KEY": "sk-test-key",
                "LLM_BASE_URL": "https://api.openai.com/v1",
                "LLM_MODEL": "gpt-4o-mini",
            },
        ):
            service = AIService()
            self.assertEqual(service.base_url, "https://api.openai.com/v1")
            self.assertEqual(service.model, "gpt-4o-mini")
            self.assertEqual(service.api_key, "sk-test-key")
            self.assertTrue(service.is_configured())

        # Explicit constructor args override env vars
        service = AIService(
            api_key="sk-override",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
        )
        self.assertEqual(service.base_url, "https://api.deepseek.com/v1")
        self.assertEqual(service.model, "deepseek-chat")
        self.assertEqual(service.api_key, "sk-override")
        self.assertTrue(service.is_configured())

        # Unconfigured state
        unconf = AIService(api_key="", base_url="")
        self.assertFalse(unconf.is_configured())

    def test_offline_fallback_when_endpoint_unavailable(self):
        """When endpoint cannot be connected (offline/down), stream_chat and chat_complete yield friendly fallback."""
        # Using a dummy unreachable port
        service = AIService(base_url="http://localhost:59999/v1", timeout=0.5)

        messages = [{"role": "user", "content": "测试连接"}]
        chunks = list(service.stream_chat(messages))

        self.assertEqual(len(chunks), 1)
        self.assertIn("未检测到可用的大模型服务或网络离线", chunks[0])
        self.assertEqual(chunks[0], OFFLINE_FALLBACK_MESSAGE)

        # chat_complete should also return the friendly fallback
        reply = service.chat_complete(messages)
        self.assertEqual(reply, OFFLINE_FALLBACK_MESSAGE)

    def test_offline_fallback_when_unconfigured(self):
        """When service has no base_url or api_key configured, fallback immediately without making request."""
        service = AIService(base_url="", api_key="")
        messages = [{"role": "user", "content": "测试未配置"}]

        chunks = list(service.stream_chat(messages))
        self.assertEqual(chunks, [OFFLINE_FALLBACK_MESSAGE])

        reply = service.chat_complete(messages)
        self.assertEqual(reply, OFFLINE_FALLBACK_MESSAGE)

    def test_stream_chat_mocked_sse(self):
        """Verify stream_chat parses OpenAI/Ollama SSE lines properly."""
        service = AIService(base_url="http://localhost:11434/v1")
        messages = [{"role": "user", "content": "你好"}]

        sse_lines = [
            b': ping\n',
            'data: {"choices":[{"delta":{"content":"同学"}}]}\n\n'.encode("utf-8"),
            'data: {"choices":[{"delta":{"content":"你好"}}]}\n\n'.encode("utf-8"),
            'data: {"choices":[{"delta":{"content":"！"}}]}\n\n'.encode("utf-8"),
            b'data: [DONE]\n\n',
        ]

        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = sse_lines
        mock_resp.__exit__.return_value = False

        with patch("urllib.request.urlopen", return_value=mock_resp):
            chunks = list(service.stream_chat(messages))

        self.assertEqual(chunks, ["同学", "你好", "！"])
        self.assertEqual("".join(chunks), "同学你好！")

    def test_chat_complete_mocked_json(self):
        """Verify chat_complete parses standard non-streaming JSON response."""
        service = AIService(base_url="http://localhost:11434/v1")
        messages = [{"role": "user", "content": "你好"}]

        resp_obj = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "做错这道题的原因在于没有区分进程与线程的隔离性。",
                    }
                }
            ]
        }
        resp_bytes = json.dumps(resp_obj).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = resp_bytes
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        with patch("urllib.request.urlopen", return_value=mock_resp):
            reply = service.chat_complete(messages)

        self.assertEqual(reply, "做错这道题的原因在于没有区分进程与线程的隔离性。")

    def test_stream_chat_http_error_graceful_handling(self):
        """Verify HTTP 500 / 401 error results in graceful fallback rather than crashing."""
        service = AIService(base_url="http://localhost:11434/v1")
        messages = [{"role": "user", "content": "你好"}]

        http_err = urllib.error.HTTPError(
            url="http://localhost:11434/v1/chat/completions",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=io.BytesIO(b'{"error": "model error"}'),
        )
        try:
            with patch("urllib.request.urlopen", side_effect=http_err):
                chunks = list(service.stream_chat(messages))
                reply = service.chat_complete(messages)

            self.assertEqual(chunks, [OFFLINE_FALLBACK_MESSAGE])
            self.assertEqual(reply, OFFLINE_FALLBACK_MESSAGE)
        finally:
            http_err.close()

    def test_services_init_exports(self):
        """Verify services package exports build_tutor_prompt and AIService."""
        import backend.services as services
        self.assertTrue(hasattr(services, "build_tutor_prompt"))
        self.assertTrue(hasattr(services, "AIService"))


if __name__ == "__main__":
    unittest.main()
