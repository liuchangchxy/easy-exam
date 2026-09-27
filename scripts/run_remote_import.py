import sys
from pathlib import Path
from backend.app.infrastructure.db.repositories.bank_repository import BankRepository
from backend.app.infrastructure.db.repositories.question_repository import QuestionRepository
from backend.app.infrastructure.db.repositories.import_job_repository import ImportJobRepository
from backend.app.infrastructure.db.repositories.user_repository import UserRepository
from backend.app.application.import_service import ImportService

db_path = "/app/data/easyexam-v1.db"
users_repo = UserRepository(db_path)
bank_repo = BankRepository(db_path)
question_repo = QuestionRepository(db_path)
import_jobs = ImportJobRepository(db_path)
importer = ImportService(bank_repo, question_repo, import_jobs)

# Pick user
all_users = users_repo.list_all() if hasattr(users_repo, "list_all") else []
user = None
if all_users:
    user = all_users[0]
else:
    # fallback from db
    import sqlite3
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT id, username FROM users LIMIT 1")
    row = cur.fetchone()
    if row:
        user = {"id": row[0], "username": row[1]}

if not user:
    print("Error: No users found in database!")
    sys.exit(1)

print(f"Using user: {user['username']} ({user['id']})")

bank_name = "全国软考·系统集成项目管理工程师历年真题（141题）"
existing_banks = bank_repo.list_for_user(user["id"])
target_bank = None
for b in existing_banks:
    if b["name"] == bank_name:
        target_bank = b
        break

if not target_bank:
    target_bank = bank_repo.create(
        user["id"],
        name=bank_name,
        description="包含全国计算机技术与软件专业技术资格（水平）考试——系统集成项目管理工程师历年单选真题与详细解析，适合完整模拟考与高频考点专项练习。",
        category="软考"
    )
    print(f"Created new bank: {bank_name} (ID: {target_bank['id']})")
else:
    print(f"Found existing bank: {bank_name} (ID: {target_bank['id']})")

md_path = Path("/tmp/ruankao_141.md")
content = md_path.read_text(encoding="utf-8")

res = importer.import_content(
    user_id=user["id"],
    bank_id=target_bank["id"],
    fmt="markdown",
    content=content,
    duplicate_strategy="merge"
)

print(f"Import success! Details: {res}")

# Check final questions count
bank_questions = question_repo.list_for_bank(target_bank["id"], user["id"])
print(f"Bank now contains {len(bank_questions)} questions.")
