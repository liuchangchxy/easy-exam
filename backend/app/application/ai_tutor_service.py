import json
import threading
from typing import Any, Dict, List, Optional


class AiTutorService:
    def __init__(self, answers, questions, provider=None, web_search=None, conversations=None, assets=None, drafts=None, ai_configs=None):
        self.answers = answers
        self.questions = questions
        self.provider = provider
        self.web_search = web_search
        self.conversations = conversations
        self.assets = assets
        self.drafts = drafts
        self.ai_configs = ai_configs
        self._batch_tasks: Dict[tuple, dict] = {}
        self._batch_lock = threading.Lock()

    def get_user_ai_config(self, user_id: str) -> dict:
        if self.ai_configs:
            return self.ai_configs.get_config(user_id, mask_secrets=True)
        return {
            "ai_provider": "openai",
            "ai_api_base": "https://api.openai.com/v1",
            "ai_model": "gpt-4o-mini",
            "ai_api_key": "",
            "search_provider": "open-webSearch",
            "search_api_key": "",
            "search_api_base": "http://localhost:8000/v1/search",
            "is_configured": False,
        }

    def save_user_ai_config(self, user_id: str, payload: dict) -> dict:
        if self.ai_configs:
            return self.ai_configs.save_config(user_id, payload)
        return self.get_user_ai_config(user_id)

    def _get_provider_for_user(self, user_id: str):
        if self.ai_configs:
            cfg = self.ai_configs.get_config(user_id, mask_secrets=False)
            if cfg.get("ai_api_key") or ("localhost" in cfg.get("ai_api_base", "")):
                from backend.legacy.services.ai_service import AIService
                from backend.app.infrastructure.ai.provider import CompatibleAiProvider
                return CompatibleAiProvider(AIService(
                    api_key=cfg.get("ai_api_key"),
                    base_url=cfg.get("ai_api_base"),
                    model=cfg.get("ai_model"),
                ))
        from backend.app.infrastructure.ai.provider import CompatibleAiProvider
        return self.provider or CompatibleAiProvider()

    def _get_search_for_user(self, user_id: str):
        if self.web_search:
            return self.web_search
        if self.ai_configs:
            cfg = self.ai_configs.get_config(user_id, mask_secrets=False)
            if cfg.get("search_provider") == "open-webSearch":
                from backend.app.infrastructure.ai.web_search import OpenWebSearchAdapter
                return OpenWebSearchAdapter(endpoint_url=cfg.get("search_api_base"))
            elif cfg.get("search_provider") == "offline":
                from backend.app.infrastructure.ai.web_search import OfflineWebSearch
                return OfflineWebSearch()
        from backend.app.infrastructure.ai.web_search import OfflineWebSearch
        return OfflineWebSearch()

    def _inject_assets_context(self, user_id: str, question: dict, base_prompt_msgs: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[str]]:
        if not self.assets:
            return base_prompt_msgs, []
        relevant = self.assets.find_relevant(user_id, question_id=question.get("id"), tags=question.get("tags"))
        if not relevant:
            return base_prompt_msgs, []

        asset_lines = []
        referenced_ids = []
        for a in relevant:
            referenced_ids.append(a["id"])
            asset_lines.append(f"- [资料ID: {a['id']}] [{a['asset_type']}] {a['content']}")
        assets_text = "\n".join(asset_lines)

        new_msgs = []
        for msg in base_prompt_msgs:
            if msg["role"] == "system":
                enriched = msg["content"] + f"\n\n【用户个人参考资料（严格隔离自用户知识库）】\n{assets_text}\n请在辅导时结合上述个人资料进行解答与点拨，并指明依据。"
                new_msgs.append({"role": "system", "content": enriched})
            else:
                new_msgs.append(msg)
        return new_msgs, referenced_ids

    def save_candidate(self, user_id: str, question_id: str, content: str, source: str = "AI", provider: str | None = None) -> dict:
        question = self.questions.get_for_user(question_id, user_id)
        if not question:
            raise LookupError("question not found")
        if source not in {"AI", "WEB", "PERSONAL"}:
            raise ValueError("candidate source must be AI, WEB, or PERSONAL")
        return self.answers.create(user_id, question, content, source, provider)

    def adopt_personal_answer(self, user_id: str, answer_id: str) -> dict:
        answer = self.answers.adopt(answer_id, user_id)
        if not answer:
            raise LookupError("answer not found")
        return answer

    def generate_answer(self, user_id: str, question_id: str, query: str = "", history=None, target_lang: str = "zh-CN") -> dict:
        question = self.questions.get_for_user(question_id, user_id)
        if not question:
            raise LookupError("question not found")
        from backend.app.infrastructure.ai.provider import build_tutor_prompt
        provider = self._get_provider_for_user(user_id)
        base_prompt = build_tutor_prompt(question, query, history, target_lang=target_lang)
        prompt_msgs, referenced_assets = self._inject_assets_context(user_id, question, base_prompt)
        content = provider.chat_complete(prompt_msgs)
        ans = self.answers.create(user_id, question, content, "AI", getattr(provider, "model", None))
        ans["referenced_assets"] = referenced_assets
        return ans

    def request_web_verification(self, user_id: str, question_id: str, query: str = "") -> dict:
        question = self.questions.get_for_user(question_id, user_id)
        if not question:
            raise LookupError("question not found")
        search = self._get_search_for_user(user_id)
        result = search.search(query.strip() or question["stem"])
        content = result.get("message") or "已取得联网核查结果，请查看来源证据。"
        if result.get("results"):
            content += "\n\n" + "\n".join(item.get("summary") or item.get("title") or "" for item in result["results"])
        answer = self.answers.create(user_id, question, content, "WEB", getattr(search, "name", None))
        evidence = self.answers.add_evidence(answer["id"], user_id, result.get("results", []))
        answer["verification_status"] = result.get("status", "VERIFIED")
        answer["evidence"] = evidence
        return answer

    def send_chat_message(
        self,
        user_id: str,
        question_id: str,
        content: str,
        conversation_id: str | None = None,
        parent_message_id: str | None = None,
        target_lang: str = "zh-CN",
    ) -> dict:
        if not self.conversations:
            raise RuntimeError("AiConversationRepository is not configured")
        question = self.questions.get_for_user(question_id, user_id)
        if not question:
            raise LookupError("question not found")
        version_id = question["version_id"]

        if conversation_id:
            conv = self.conversations.get_conversation(conversation_id, user_id)
            if not conv:
                raise LookupError("conversation not found or forbidden")
        else:
            conv = self.conversations.get_or_create_active_conversation(user_id, question_id, version_id)
            conversation_id = conv["id"]

        user_msg = self.conversations.append_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role="user",
            content=content,
            parent_message_id=parent_message_id,
            status="success",
        )

        if parent_message_id:
            thread = self.conversations.get_message_thread(parent_message_id, user_id)
            history = [{"role": m["role"], "content": m["content"]} for m in thread]
        else:
            all_msgs = self.conversations.list_messages(conversation_id, user_id)
            history = [{"role": m["role"], "content": m["content"]} for m in all_msgs if m["id"] != user_msg["id"]]

        from backend.app.infrastructure.ai.provider import build_tutor_prompt
        provider = self._get_provider_for_user(user_id)
        base_prompt = build_tutor_prompt(question, content, history, target_lang=target_lang)
        prompt_msgs, referenced_assets = self._inject_assets_context(user_id, question, base_prompt)
        assistant_content = provider.chat_complete(prompt_msgs)

        assistant_msg = self.conversations.append_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role="assistant",
            content=assistant_content,
            parent_message_id=user_msg["id"],
            status="success",
        )
        assistant_msg["referenced_assets"] = referenced_assets

        return {
            "conversation": conv,
            "user_message": user_msg,
            "assistant_message": assistant_msg,
        }

    def list_conversations(self, user_id: str, question_id: str, question_version_id: str | None = None) -> list[dict]:
        if not self.conversations:
            return []
        return self.conversations.list_conversations_for_question(user_id, question_id, question_version_id)

    def list_messages(self, user_id: str, conversation_id: str) -> list[dict]:
        if not self.conversations:
            raise LookupError("conversation repository not configured")
        return self.conversations.list_messages(conversation_id, user_id)

    def get_message_thread(self, user_id: str, message_id: str) -> list[dict]:
        if not self.conversations:
            raise LookupError("conversation repository not configured")
        return self.conversations.get_message_thread(message_id, user_id)

    # --- EE-005 AI Variant Draft Workflow ---

    def generate_variant_draft(
        self,
        user_id: str,
        original_question_id: str,
        target_bank_id: str,
        prompt_hint: str = "",
    ) -> dict:
        if not self.drafts:
            raise RuntimeError("AiDraftRepository is not configured")
        original = self.questions.get_for_user(original_question_id, user_id)
        if not original:
            raise LookupError("original question not found")

        from backend.app.infrastructure.ai.provider import CompatibleAiProvider
        provider = self.provider or CompatibleAiProvider()

        variant_prompt = [
            {
                "role": "system",
                "content": (
                    "你是一位严谨的出题专家。请基于给出的原题生成一道考查相同知识点的变式题。"
                    "要求输出纯 JSON 对象，格式包含：stem (题干字符串), type (SINGLE 或 MULTIPLE 或 JUDGE 或 QA), "
                    "options (选项列表，格式如 [{'key': 'A', 'text': '...'}, {'key': 'B', 'text': '...'}]), "
                    "answer (正确答案), explanation (详细解析), difficulty (1-5 整数), tags (字符串标签列表)。"
                ),
            },
            {
                "role": "user",
                "content": f"原题题干: {original.get('stem')}\n原题选项: {json.dumps(original.get('options') or [], ensure_ascii=False)}\n原题答案: {original.get('answer')}\n原题解析: {original.get('explanation')}\n出题要求: {prompt_hint or '生成考点相同的变式题'}",
            },
        ]

        raw_output = provider.chat_complete(variant_prompt)
        draft_payload = None
        try:
            cleaned = raw_output.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            draft_payload = json.loads(cleaned)
        except Exception:
            draft_payload = {
                "stem": f"【变式】{original.get('stem')}",
                "type": original.get("type", "SINGLE"),
                "options": original.get("options", []),
                "answer": original.get("answer", ""),
                "explanation": f"基于原题考点的变式题解析：{original.get('explanation', '')}",
                "difficulty": original.get("difficulty", 3),
                "tags": original.get("tags", []),
            }

        return self.drafts.create_draft(user_id, original_question_id, target_bank_id, draft_payload)

    def list_variant_drafts(self, user_id: str, status: str = "DRAFT") -> list[dict]:
        if not self.drafts:
            return []
        return self.drafts.list_drafts(user_id, status)

    def get_variant_draft(self, user_id: str, draft_id: str) -> dict:
        if not self.drafts:
            raise LookupError("AiDraftRepository is not configured")
        draft = self.drafts.get_draft(user_id, draft_id)
        if not draft:
            raise LookupError("draft not found")
        return draft

    def accept_variant_draft(self, user_id: str, draft_id: str, modifications: Optional[dict] = None) -> dict:
        if not self.drafts:
            raise LookupError("AiDraftRepository is not configured")
        draft = self.drafts.get_draft(user_id, draft_id)
        if not draft or draft.get("status") != "DRAFT":
            raise LookupError("draft not found or already processed")

        payload = {
            "stem": (modifications.get("stem") if modifications and "stem" in modifications else draft["stem"]),
            "type": (modifications.get("type") if modifications and "type" in modifications else draft["type"]),
            "options": (modifications.get("options") if modifications and "options" in modifications else draft["options"]),
            "answer": (modifications.get("answer") if modifications and "answer" in modifications else draft["answer"]),
            "explanation": (modifications.get("explanation") if modifications and "explanation" in modifications else draft["explanation"]),
            "difficulty": (modifications.get("difficulty") if modifications and "difficulty" in modifications else draft["difficulty"]),
            "tags": (modifications.get("tags") if modifications and "tags" in modifications else draft["tags"]),
        }

        # Create question into target bank
        official_question = self.questions.create_versioned_question(user_id, draft["target_bank_id"], payload)
        self.drafts.update_status(user_id, draft_id, "ACCEPTED")
        return {
            "status": "ACCEPTED",
            "draft_id": draft_id,
            "question": official_question,
        }

    def discard_variant_draft(self, user_id: str, draft_id: str) -> dict:
        if not self.drafts:
            raise LookupError("AiDraftRepository is not configured")
        updated = self.drafts.update_status(user_id, draft_id, "DISCARDED")
        if not updated:
            raise LookupError("draft not found")
        return {"status": "DISCARDED", "draft_id": draft_id}

    def get_batch_status(self, user_id: str, bank_id: str) -> dict:
        with self._batch_lock:
            task = self._batch_tasks.get((user_id, bank_id))
            if task and task["status"] in ("running", "stopping"):
                return {**task}

            all_questions = self.questions.list_for_bank(bank_id, user_id)
            with_explanation = 0
            for q in all_questions:
                if q.get("explanation") or bool(self.answers.list_for_question(q["id"], user_id)):
                    with_explanation += 1
            base = {
                "status": task["status"] if task else "idle",
                "total": len(all_questions),
                "with_explanation": with_explanation,
                "without_explanation": len(all_questions) - with_explanation,
                "processed": task["processed"] if task else 0,
                "succeeded": task["succeeded"] if task else 0,
                "failed": task["failed"] if task else 0,
                "current_question_stem": task["current_question_stem"] if task else "",
            }
            return base

    def start_batch_generate(self, user_id: str, bank_id: str, overwrite: bool = False, target_lang: str = "zh-CN") -> dict:
        with self._batch_lock:
            existing = self._batch_tasks.get((user_id, bank_id))
            if existing and existing["status"] == "running":
                return {**existing}

            all_questions = self.questions.list_for_bank(bank_id, user_id)
            if not overwrite:
                targets = [
                    q for q in all_questions
                    if not q.get("explanation") and not bool(self.answers.list_for_question(q["id"], user_id))
                ]
            else:
                targets = all_questions

            task = {
                "status": "running",
                "total": len(targets),
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "current_question_stem": "",
                "stop_requested": False,
                "error": None,
            }
            self._batch_tasks[(user_id, bank_id)] = task

        if not targets:
            with self._batch_lock:
                task["status"] = "completed"
            return {**task}

        def worker():
            for q in targets:
                with self._batch_lock:
                    if task["stop_requested"]:
                        task["status"] = "stopped"
                        return
                    task["current_question_stem"] = q.get("stem", "")[:60]
                try:
                    self.generate_answer(user_id, q["id"], target_lang=target_lang)
                    with self._batch_lock:
                        task["succeeded"] += 1
                except Exception as exc:
                    with self._batch_lock:
                        task["failed"] += 1
                finally:
                    with self._batch_lock:
                        task["processed"] += 1
            with self._batch_lock:
                task["status"] = "completed"
                task["current_question_stem"] = ""

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        return {**task}

    def stop_batch_generate(self, user_id: str, bank_id: str) -> dict:
        with self._batch_lock:
            task = self._batch_tasks.get((user_id, bank_id))
            if task and task["status"] == "running":
                task["stop_requested"] = True
                task["status"] = "stopping"
                return {**task}
            return task or {"status": "idle"}

