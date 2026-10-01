import json
import re
from pathlib import Path

import os
import sys

content_path = os.environ.get("EXTRACT_CONTENT_PATH") or (sys.argv[1] if len(sys.argv) > 1 else "content.md")
content_file = Path(content_path)
if not content_file.exists():
    print(f"Extraction file not found: {content_file}")
    sys.exit(0)
text = content_file.read_text(encoding="utf-8")

matches = list(re.finditer(r'\{\s*"id":\s*"[^"]+",\s*"noteId":', text))
print(f"Found question blocks: {len(matches)}")

questions = []
for i in range(len(matches)):
    start = matches[i].start()
    end = matches[i + 1].start() if i + 1 < len(matches) else text.rfind("}")
    chunk = text[start:end].rstrip(", \r\n\t")
    last_brace = chunk.rfind("}")
    if last_brace != -1:
        chunk = chunk[: last_brace + 1]
    try:
        q = json.loads(chunk)
        stem = q.get("stem", "").strip()
        opts = q.get("options", [])
        ans = q.get("answer", "").strip()
        exp = q.get("explanation", "").strip()

        # Filter corrupted or non-multiple-choice
        if "抓取失败" in stem or len(opts) < 2 or ans not in ("A", "B", "C", "D", "AB", "AC", "AD", "BC", "BD", "CD", "ABC", "ABCD"):
            continue

        clean_stem = stem.replace("\xa0", " ").replace("\\*", "").replace("\\_", "_").strip()
        # Remove leading numbers like "1.", "14." if present
        clean_stem = re.sub(r"^\d+[\.、．\s]+", "", clean_stem).strip()
        if len(clean_stem) < 3:
            continue

        clean_opts = []
        for opt in opts:
            letter = opt.get("letter", "").strip().upper()
            ot = opt.get("text", "").replace("\xa0", " ").replace("\\*", "").replace("\\_", "_").strip()
            # Remove redundant option letter inside text
            ot = re.sub(r"^[A-Ha-h][\.、．\s]+", "", ot)
            clean_opts.append({"letter": letter, "text": ot})

        clean_exp = exp.replace("\xa0", " ").strip()
        category = q.get("yearTitle", "全国软考系统集成项目管理工程师真题")

        questions.append({
            "stem": clean_stem,
            "options": clean_opts,
            "answer": ans,
            "explanation": clean_exp,
            "category": category,
            "difficulty": 3,
        })
    except Exception:
        continue

print(f"Extracted {len(questions)} high quality questions.")

# 1. Output Markdown format
out_dir = Path("data")
out_dir.mkdir(parents=True, exist_ok=True)
md_path = out_dir / "ruankao_system_integration_142.md"
json_path = out_dir / "ruankao_system_integration_142.json"

md_lines = []
for idx, q in enumerate(questions, 1):
    md_lines.append(f"{idx}. {q['stem']}")
    for opt in q["options"]:
        md_lines.append(f"{opt['letter']}. {opt['text']}")
    md_lines.append(f"答案：{q['answer']}")
    if q["explanation"]:
        # single line or indented explanation
        flat_exp = " ".join(line.strip() for line in q["explanation"].splitlines() if line.strip())
        md_lines.append(f"解析：{flat_exp}")
    md_lines.append("难度：3")
    md_lines.append("标签：软考, 系统集成项目管理工程师")
    md_lines.append("")

md_path.write_text("\n".join(md_lines), encoding="utf-8")
print(f"Saved Markdown bank to: {md_path}")

# 2. Output JSON format
json_data = []
for q in questions:
    json_data.append({
        "stem": q["stem"],
        "options": [{"key": opt["letter"], "content": opt["text"]} for opt in q["options"]],
        "answer": q["answer"],
        "explanation": q["explanation"],
        "difficulty": 3,
        "tags": ["软考", "系统集成项目管理工程师"]
    })

json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Saved JSON bank to: {json_path}")
