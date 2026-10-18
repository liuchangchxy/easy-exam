import json
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


@pytest.fixture
def client_and_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    app = create_app(db_path=db_path)
    client = TestClient(app)
    try:
        yield client, db_path
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def _register_and_login(client, username, password="Password123!"):
    resp = client.post("/api/v1/auth/register", json={"username": username, "password": password})
    assert resp.status_code == 201, resp.text
    login_resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["token"]
    user_id = login_resp.json()["user"]["id"]
    return token, user_id


def test_bank_content_questions_api_and_guards(client_and_db):
    client, db_path = client_and_db

    # 1. Setup admin and member users
    admin_token, admin_id = _register_and_login(client, "admin_user")
    member_token, member_id = _register_and_login(client, "member_user")
    stranger_token, stranger_id = _register_and_login(client, "stranger_user")

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    member_headers = {"Authorization": f"Bearer {member_token}"}
    stranger_headers = {"Authorization": f"Bearer {stranger_token}"}

    # 2. Admin creates a bank
    create_bank_resp = client.post(
        "/api/v1/banks",
        json={"name": "Content Test Bank", "category": "CS", "description": "Bank for content mgmt test"},
        headers=admin_headers,
    )
    assert create_bank_resp.status_code == 201
    bank_id = create_bank_resp.json()["id"]

    # 3. Add member to bank
    add_member_resp = client.post(
        f"/api/v1/banks/{bank_id}/members",
        json={"username": "member_user", "role": "MEMBER"},
        headers=admin_headers,
    )
    assert add_member_resp.status_code == 201

    # 4. Create 2 questions
    q1_resp = client.post(
        f"/api/v1/banks/{bank_id}/questions",
        json={
            "stem": "What is 2+2?",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "3"}, {"key": "B", "content": "4"}],
            "answer": "B",
            "explanation": "2+2=4",
            "difficulty": 1,
            "tags": ["math", "basic"],
        },
        headers=admin_headers,
    )
    assert q1_resp.status_code == 201
    q1_id = q1_resp.json()["id"]

    q2_resp = client.post(
        f"/api/v1/banks/{bank_id}/questions",
        json={
            "stem": "Is Python interpreted?",
            "type": "JUDGE",
            "options": [{"key": "T", "content": "True"}, {"key": "F", "content": "False"}],
            "answer": "T",
            "explanation": "Python is an interpreted language",
            "difficulty": 2,
            "tags": ["python"],
        },
        headers=admin_headers,
    )
    assert q2_resp.status_code == 201
    q2_id = q2_resp.json()["id"]

    # 5. Member reads content questions
    member_content_resp = client.get(f"/api/v1/banks/{bank_id}/content/questions", headers=member_headers)
    assert member_content_resp.status_code == 200, member_content_resp.text
    content_questions = member_content_resp.json()
    assert len(content_questions) == 2
    stems = {q["stem"] for q in content_questions}
    assert "What is 2+2?" in stems
    assert "Is Python interpreted?" in stems

    # 6. Stranger (non-member) cannot access content questions (404 or 403)
    stranger_resp = client.get(f"/api/v1/banks/{bank_id}/content/questions", headers=stranger_headers)
    assert stranger_resp.status_code in (403, 404)

    # 7. Member kills question 1
    kill_resp = client.post(f"/api/v1/kills/{q1_id}", headers=member_headers)
    assert kill_resp.status_code == 201

    # In practice list (list_for_bank), question 1 is excluded for this member
    practice_list_resp = client.get(f"/api/v1/banks/{bank_id}/questions", headers=member_headers)
    assert practice_list_resp.status_code == 200
    practice_qids = [q["id"] for q in practice_list_resp.json()]
    assert q1_id not in practice_qids
    assert q2_id in practice_qids

    # BUT in content questions list, question 1 MUST STILL BE PRESENT!
    member_content_after_kill = client.get(f"/api/v1/banks/{bank_id}/content/questions", headers=member_headers)
    assert member_content_after_kill.status_code == 200
    content_qids_after_kill = [q["id"] for q in member_content_after_kill.json()]
    assert q1_id in content_qids_after_kill
    assert q2_id in content_qids_after_kill

    # 8. Admin updates question 1 generating version 2
    put_resp = client.put(
        f"/api/v1/questions/{q1_id}",
        json={
            "stem": "What is 2 + 2 exactly?",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "3"}, {"key": "B", "content": "4"}],
            "answer": "B",
            "explanation": "2+2=4 always",
            "difficulty": 1,
            "tags": ["math", "arithmetic"],
            "base_version_number": 1,
            "regrade_history": False,
        },
        headers=admin_headers,
    )
    assert put_resp.status_code == 200, put_resp.text
    updated_q1 = put_resp.json()
    assert updated_q1["version_number"] == 2
    assert updated_q1["stem"] == "What is 2 + 2 exactly?"

    # Member cannot edit question (returns 403)
    member_put_resp = client.put(
        f"/api/v1/questions/{q1_id}",
        json={
            "stem": "Hacked stem by member",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "3"}, {"key": "B", "content": "4"}],
            "answer": "A",
            "base_version_number": 2,
        },
        headers=member_headers,
    )
    assert member_put_resp.status_code == 403

    # 9. Active exam safety:
    # Admin starts an active EXAM containing q2
    exam_start_resp = client.post(
        "/api/v1/practice/sessions",
        json={"bank_id": bank_id, "mode": "EXAM", "total_questions": 1, "question_ids": [q2_id]},
        headers=admin_headers,
    )
    assert exam_start_resp.status_code == 201
    exam_session = exam_start_resp.json()
    assert exam_session["is_completed"] == 0

    # When admin queries content/questions, q2 answer and explanation must be masked
    admin_content_during_exam = client.get(f"/api/v1/banks/{bank_id}/content/questions", headers=admin_headers)
    assert admin_content_during_exam.status_code == 200
    q2_item = next(q for q in admin_content_during_exam.json() if q["id"] == q2_id)
    assert q2_item["answer"] == ""
    assert q2_item["explanation"] == ""

    # Attempting to edit q2 while active exam is running must be rejected
    exam_q_edit_resp = client.put(
        f"/api/v1/questions/{q2_id}",
        json={
            "stem": "Tampered question during exam",
            "type": "JUDGE",
            "options": [{"key": "T", "content": "True"}, {"key": "F", "content": "False"}],
            "answer": "T",
            "base_version_number": 1,
        },
        headers=admin_headers,
    )
    assert exam_q_edit_resp.status_code == 403
