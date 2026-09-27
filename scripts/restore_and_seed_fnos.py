import sys
import uuid
from pathlib import Path
import sqlite3

from backend.app.infrastructure.db.connection import migrate
from backend.app.infrastructure.security.password import hash_password
from backend.app.infrastructure.db.repositories.bank_repository import BankRepository
from backend.app.infrastructure.db.repositories.question_repository import QuestionRepository
from backend.app.infrastructure.db.repositories.import_job_repository import ImportJobRepository
from backend.app.infrastructure.db.repositories.user_repository import UserRepository
from backend.app.application.import_service import ImportService

db_path = "/app/data/easyexam-v1.db"

print(f"Ensuring database migrations at {db_path}...")
migrate(db_path)

users_repo = UserRepository(db_path)
bank_repo = BankRepository(db_path)
question_repo = QuestionRepository(db_path)
import_jobs = ImportJobRepository(db_path)
importer = ImportService(bank_repo, question_repo, import_jobs)

# Preset accounts
accounts_to_ensure = [
    ("admin", "REDACTED_ADMIN_PASSWORD"),
    ("chang", "REDACTED_TEST_PASSWORD"),
]

target_users = []
for uname, upass in accounts_to_ensure:
    existing_u = users_repo.get_by_username(uname)
    if existing_u:
        target_users.append(existing_u)
        print(f"User {uname} already exists with id {existing_u['id']}")
    else:
        hashed = hash_password(upass)
        new_u = users_repo.create(uname, hashed)
        target_users.append(new_u)
        print(f"Created user {uname} with id {new_u['id']}")

# Import 141 questions bank for users
md_path = Path("/tmp/ruankao_141.md")
if not md_path.exists():
    print(f"Error: {md_path} does not exist!")
    sys.exit(1)

content = md_path.read_text(encoding="utf-8")
bank_name = "全国软考·系统集成项目管理工程师历年真题（141题）"

for u in target_users:
    existing_banks = bank_repo.list_for_user(u["id"])
    target_bank = next((b for b in existing_banks if b["name"] == bank_name), None)
    if not target_bank:
        target_bank = bank_repo.create(
            u["id"],
            name=bank_name,
            description="包含全国计算机技术与软件专业技术资格（水平）考试——系统集成项目管理工程师历年单选真题与详细解析，适合完整模拟考与高频考点专项练习。",
            category="软考"
        )
        print(f"Created bank for user {u['username']}: {bank_name} (ID: {target_bank['id']})")
    else:
        print(f"User {u['username']} already has bank: {bank_name} (ID: {target_bank['id']})")

    existing_q_count = len(question_repo.list_for_bank(target_bank["id"], u["id"]))
    if existing_q_count < 140:
        print(f"Importing questions into bank {target_bank['id']} for user {u['username']}...")
        res = importer.import_content(
            user_id=u["id"],
            bank_id=target_bank["id"],
            fmt="markdown",
            content=content,
            duplicate_strategy="merge"
        )
        print(f"Import finished for {u['username']}: {res}")
    else:
        print(f"Bank already contains {existing_q_count} questions for {u['username']}, skipping import.")

print("\nAll target users and 141-question banks successfully ensured and ready!")
