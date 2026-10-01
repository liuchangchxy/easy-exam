import sqlite3

conn = sqlite3.connect("/vol4/@appdata/easy-exam/easyexam-v1.db")
row = conn.execute("SELECT id FROM users WHERE username='u_test_9435'").fetchone()
if not row:
    print("User not found!")
    exit(1)
target_uid = row[0]
banks = conn.execute("SELECT id FROM question_banks WHERE is_deleted=0").fetchall()
for (bid,) in banks:
    conn.execute(
        "INSERT OR REPLACE INTO question_bank_members (bank_id, user_id, role) VALUES (?, ?, 'ADMIN')",
        (bid, target_uid)
    )
conn.commit()
count = conn.execute("SELECT COUNT(*) FROM question_bank_members WHERE user_id=?", (target_uid,)).fetchone()[0]
print("TOTAL_BANKS_FOR_AUDIT_USER:", count)
