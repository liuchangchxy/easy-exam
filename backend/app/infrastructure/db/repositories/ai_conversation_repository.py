# Portions of this file are derived from MiaowTest (https://github.com/qijun1900/miaowtest)
# commit 803dadcf14a9bcb5e62deba237e15e90641a9d5a
# Copyright (c) 2026 qijun1900, licensed under the MIT License.
#
# Provides version-isolated AI tutor conversations, multi-turn sequential messages,
# and tree/branching recovery via parent_message_id without independent chatroom bloat.

import uuid
from typing import Any, Dict, List, Optional
from backend.app.infrastructure.db.connection import get_connection, transaction


class AiConversationRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def create_conversation(
        self,
        user_id: str,
        question_id: str,
        question_version_id: str,
        title: str = "",
    ) -> Dict[str, Any]:
        conv_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            conn.execute(
                """INSERT INTO ai_conversations(id, user_id, question_id, question_version_id, title)
                   VALUES (?, ?, ?, ?, ?)""",
                (conv_id, user_id, question_id, question_version_id, title or ""),
            )
        return self.get_conversation(conv_id, user_id)  # type: ignore

    def get_conversation(self, conversation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                """SELECT id, user_id, question_id, question_version_id, title, created_at, updated_at
                   FROM ai_conversations WHERE id = ? AND user_id = ?""",
                (conversation_id, user_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_conversations_for_question(
        self,
        user_id: str,
        question_id: str,
        question_version_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        try:
            if question_version_id:
                rows = conn.execute(
                    """SELECT id, user_id, question_id, question_version_id, title, created_at, updated_at
                       FROM ai_conversations
                       WHERE user_id = ? AND question_id = ? AND question_version_id = ?
                       ORDER BY created_at DESC""",
                    (user_id, question_id, question_version_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, user_id, question_id, question_version_id, title, created_at, updated_at
                       FROM ai_conversations
                       WHERE user_id = ? AND question_id = ?
                       ORDER BY created_at DESC""",
                    (user_id, question_id),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_or_create_active_conversation(
        self,
        user_id: str,
        question_id: str,
        question_version_id: str,
    ) -> Dict[str, Any]:
        convs = self.list_conversations_for_question(user_id, question_id, question_version_id)
        if convs:
            return convs[0]
        return self.create_conversation(user_id, question_id, question_version_id)

    def append_message(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        parent_message_id: Optional[str] = None,
        status: str = "success",
    ) -> Dict[str, Any]:
        if role not in ("user", "assistant", "system"):
            raise ValueError(f"Invalid role: {role}")
        if status not in ("sending", "success", "error"):
            raise ValueError(f"Invalid message status: {status}")

        msg_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            conv = conn.execute(
                "SELECT id FROM ai_conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user_id),
            ).fetchone()
            if not conv:
                raise LookupError("conversation not found or forbidden")

            if parent_message_id:
                p_row = conn.execute(
                    "SELECT id FROM ai_messages WHERE id = ? AND conversation_id = ?",
                    (parent_message_id, conversation_id),
                ).fetchone()
                if not p_row:
                    raise LookupError("parent message not found in this conversation")

            max_seq = conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) FROM ai_messages WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()[0]
            next_seq = max_seq + 1

            conn.execute(
                """INSERT INTO ai_messages(id, conversation_id, sequence, role, content, parent_message_id, message_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (msg_id, conversation_id, next_seq, role, content, parent_message_id, status),
            )
            conn.execute(
                "UPDATE ai_conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (conversation_id,),
            )

        return self.get_message(msg_id, user_id)  # type: ignore

    def get_message(self, message_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                """SELECT m.id, m.conversation_id, m.sequence, m.role, m.content,
                          m.parent_message_id, m.message_status, m.created_at
                   FROM ai_messages m
                   JOIN ai_conversations c ON m.conversation_id = c.id
                   WHERE m.id = ? AND c.user_id = ?""",
                (message_id, user_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_messages(self, conversation_id: str, user_id: str) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        try:
            conv = conn.execute(
                "SELECT id FROM ai_conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user_id),
            ).fetchone()
            if not conv:
                raise LookupError("conversation not found or forbidden")

            rows = conn.execute(
                """SELECT id, conversation_id, sequence, role, content,
                          parent_message_id, message_status, created_at
                   FROM ai_messages
                   WHERE conversation_id = ?
                   ORDER BY sequence ASC""",
                (conversation_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_message_thread(self, message_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Walk up parent_message_id chain and return messages in root-to-leaf chronological order."""
        leaf = self.get_message(message_id, user_id)
        if not leaf:
            raise LookupError("message not found or forbidden")

        conn = get_connection(self.db_path)
        try:
            thread = [leaf]
            curr_parent = leaf.get("parent_message_id")
            while curr_parent:
                p_row = conn.execute(
                    """SELECT m.id, m.conversation_id, m.sequence, m.role, m.content,
                              m.parent_message_id, m.message_status, m.created_at
                       FROM ai_messages m
                       JOIN ai_conversations c ON m.conversation_id = c.id
                       WHERE m.id = ? AND c.user_id = ?""",
                    (curr_parent, user_id),
                ).fetchone()
                if not p_row:
                    break
                p_dict = dict(p_row)
                thread.append(p_dict)
                curr_parent = p_dict.get("parent_message_id")
            thread.reverse()
            return thread
        finally:
            conn.close()
