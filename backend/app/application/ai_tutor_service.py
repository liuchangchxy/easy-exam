class AiTutorService:
    def __init__(self, answers, questions, provider=None, web_search=None, conversations=None):
        self.answers = answers
        self.questions = questions
        self.provider = provider
        self.web_search = web_search
        self.conversations = conversations

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

    def generate_answer(self, user_id: str, question_id: str, query: str = "", history=None) -> dict:
        question = self.questions.get_for_user(question_id, user_id)
        if not question:
            raise LookupError("question not found")
        from backend.app.infrastructure.ai.provider import CompatibleAiProvider, build_tutor_prompt
        provider = self.provider or CompatibleAiProvider()
        content = provider.chat_complete(build_tutor_prompt(question, query, history))
        return self.answers.create(user_id, question, content, "AI", getattr(provider, "model", None))

    def request_web_verification(self, user_id: str, question_id: str, query: str = "") -> dict:
        question = self.questions.get_for_user(question_id, user_id)
        if not question:
            raise LookupError("question not found")
        from backend.app.infrastructure.ai.web_search import OfflineWebSearch
        search = self.web_search or OfflineWebSearch()
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
    ) -> dict:
        """Adapted from MiaowTest (commit 803dadc, MIT License).

        Appends user message, calls AI provider with question context and message thread history,
        and saves assistant message in sequence with parent_message_id reference.
        """
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

        # Build history for provider prompt
        if parent_message_id:
            thread = self.conversations.get_message_thread(parent_message_id, user_id)
            history = [{"role": m["role"], "content": m["content"]} for m in thread]
        else:
            all_msgs = self.conversations.list_messages(conversation_id, user_id)
            history = [{"role": m["role"], "content": m["content"]} for m in all_msgs if m["id"] != user_msg["id"]]

        from backend.app.infrastructure.ai.provider import CompatibleAiProvider, build_tutor_prompt
        provider = self.provider or CompatibleAiProvider()
        prompt_msgs = build_tutor_prompt(question, content, history)
        assistant_content = provider.chat_complete(prompt_msgs)

        assistant_msg = self.conversations.append_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role="assistant",
            content=assistant_content,
            parent_message_id=user_msg["id"],
            status="success",
        )

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
