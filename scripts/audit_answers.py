import json
import re

import os
import sys

path = os.environ.get("AUDIT_CONTENT_PATH") or (sys.argv[1] if len(sys.argv) > 1 else "content.md")
if not os.path.exists(path):
    print(f"Audit file not found: {path}")
    sys.exit(0)
text = open(path, encoding="utf-8").read()

matches = list(re.finditer(r'\{\s*"id":\s*"[^"]+",\s*"noteId":', text))
ai_modified_count = 0
diff_raw_count = 0
examples = []

for i in range(len(matches)):
    start = matches[i].start()
    end = matches[i + 1].start() if i + 1 < len(matches) else text.rfind("}")
    chunk = text[start:end].rstrip(", \r\n\t")
    last_brace = chunk.rfind("}")
    if last_brace != -1:
        chunk = chunk[: last_brace + 1]
    try:
        q = json.loads(chunk)
        ans = q.get("answer", "").strip()
        ans_raw = q.get("answerRaw", "").strip()
        exp = q.get("explanation", "").strip()
        source = q.get("sourceTitle", "")

        if "AI参考" in source or "复核状态" in exp:
            ai_modified_count += 1
        if ans_raw and ans != ans_raw:
            diff_raw_count += 1
            examples.append({
                "stem": q.get("stem"),
                "answer": ans,
                "answerRaw": ans_raw,
                "exp": exp
            })
    except Exception:
        pass

print(f"Total parsed: {len(matches)}")
print(f"Contains AI reference / review in source or exp: {ai_modified_count}")
print(f"Answer differs from raw answer: {diff_raw_count}")
for ex in examples[:5]:
    print("DIFF EXAMPLE:", ex)
