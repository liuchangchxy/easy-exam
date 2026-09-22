"""Bank Ingestion Pipeline for fn-exam.

Implements robust parsers for plain text/Markdown (regex state machine),
CSV (flexible column aliases and encoding tolerance), and JSON.
"""
import csv
import io
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union

JUDGE_TRUE_VALUES = {"T", "TRUE", "1", "正确", "对", "YES", "Y", "✓", "✔"}
JUDGE_FALSE_VALUES = {"F", "FALSE", "0", "错误", "错", "NO", "N", "✗", "✘", "X"}

# State machine states
STATE_IDLE = "IDLE"
STATE_STEM = "STEM"
STATE_OPTION = "OPTION"
STATE_ANSWER = "ANSWER"
STATE_EXPLANATION = "EXPLANATION"

# Regex patterns for text parsing
Q_START_RE = re.compile(
    r'^(?:'
    r'第\s*(\d+)\s*题[.:：、\s]?\s*|'
    r'[【\[（(]\s*(\d+)\s*[】\]）)][.．、:：\s]?\s*|'
    r'(\d+)\s*[.．、)）:：]\s*|'
    r'(\d+)\s+(?=\S)'
    r')(.*)$'
)

OPT_START_RE = re.compile(
    r'^(?:'
    r'[【\[（(]\s*([A-Ha-h])\s*[】\]）)][.．、:：\s]?\s*|'
    r'([A-Ha-h])\s*[.．、)）:：]\s*|'
    r'([A-Ha-h])\s+(?=\S)'
    r')(.*)$'
)

ANSWER_PREFIX_RE = re.compile(
    r'^(?:'
    r'【\s*(?:答案|正解|参考答案|正确答案|Answer)\s*】|'
    r'(?:答案|正解|参考答案|正确答案|Answer|Key)\s*[:：]|'
    r'\b(?:Answer|Key)\b\s*[:：]?'
    r')\s*(.*)$',
    re.IGNORECASE
)

EXPLANATION_PREFIX_RE = re.compile(
    r'^(?:'
    r'【\s*(?:解析|分析|答案解析|试题解析|考点|Explanation|Analysis)\s*】|'
    r'(?:解析|分析|答案解析|试题解析|考点|Explanation|Analysis)\s*[:：]|'
    r'\b(?:Explanation|Analysis)\b\s*[:：]?'
    r')\s*(.*)$',
    re.IGNORECASE
)

DIFFICULTY_PREFIX_RE = re.compile(
    r'^(?:【\s*(?:难度|Difficulty)\s*】|(?:难度|Difficulty)\s*[:：])\s*(\d+)',
    re.IGNORECASE
)

TAGS_PREFIX_RE = re.compile(
    r'^(?:【\s*(?:标签|Tags|Tag|考点|分类)\s*】|(?:标签|Tags|Tag|考点|分类)\s*[:：])\s*(.*)$',
    re.IGNORECASE
)


def _normalize_judge_value(val: str) -> Optional[str]:
    """Normalize judge answer to 'T' or 'F' if recognized."""
    clean = val.strip().upper()
    if clean in JUDGE_TRUE_VALUES:
        return "T"
    if clean in JUDGE_FALSE_VALUES:
        return "F"
    return None


def infer_type_and_answer(
    explicit_type: str,
    raw_answer: str,
    options: List[Dict[str, str]],
    stem: str = ""
) -> Tuple[str, str]:
    """Infer QuestionType ('SINGLE', 'MULTI', 'JUDGE', 'ESSAY') and normalize answer.

    Rules from SPEC:
    1. If answer has >1 option letters (e.g. 'AB', 'BCD'): MULTI
    2. If answer is T/F/对/错/正确/错误: JUDGE
    3. Otherwise: SINGLE (or ESSAY if no options and text answer)
    """
    clean_ans = raw_answer.strip()
    norm_judge = _normalize_judge_value(clean_ans)

    # 1. Check if explicit type was specified
    if explicit_type:
        exp_upper = explicit_type.strip().upper()
        if exp_upper in ("SINGLE", "单选", "单选题"):
            return "SINGLE", clean_ans
        if exp_upper in ("MULTI", "多选", "多选题"):
            letters = [c for c in clean_ans.upper() if 'A' <= c <= 'H']
            return "MULTI", "".join(sorted(set(letters))) if letters else clean_ans
        if exp_upper in ("JUDGE", "判断", "判断题"):
            return "JUDGE", norm_judge if norm_judge is not None else clean_ans
        if exp_upper in ("ESSAY", "问答", "问答题", "简答", "简答题"):
            return "ESSAY", clean_ans

    # 2. Check if answer matches judge values
    if norm_judge is not None:
        return "JUDGE", norm_judge

    # 3. Check option letters in answer
    letters = [c for c in clean_ans.upper() if 'A' <= c <= 'H']

    if len(letters) > 1:
        return "MULTI", "".join(sorted(set(letters)))

    if len(letters) == 1:
        # Check if options are true/false pairs (A: 对, B: 错)
        if len(options) == 2:
            o1 = options[0].get("content", "").strip()
            o2 = options[1].get("content", "").strip()
            if (o1 in JUDGE_TRUE_VALUES and o2 in JUDGE_FALSE_VALUES) or \
               (o2 in JUDGE_TRUE_VALUES and o1 in JUDGE_FALSE_VALUES):
                target_letter = letters[0]
                matched_opt = next((o for o in options if o.get("key") == target_letter), None)
                if matched_opt:
                    opt_norm = _normalize_judge_value(matched_opt.get("content", ""))
                    if opt_norm is not None:
                        return "JUDGE", opt_norm
        return "SINGLE", letters[0]

    # 4. No option letters found
    if not options:
        return "ESSAY", clean_ans

    return "SINGLE", clean_ans


def _split_inline_options(line: str) -> Optional[List[Tuple[str, str]]]:
    """Check if a line contains multiple sequential options like 'A. 1 B. 2 C. 3 D. 4'."""
    # Matches option patterns like 'A. ...' or '(A) ...'
    pattern = re.compile(
        r'(?:^|\s{2,}|\t|\s+(?=[B-Hb-h][.．、)）:：\s]|[【\[（(][B-Hb-h][】\]）]))'
        r'(?:[【\[（(]\s*([A-Ha-h])\s*[】\]）)][.．、:：\s]?|([A-Ha-h])\s*[.．、)）:：]|([A-Ha-h])\s+)'
        r'(.*?)(?=(?:\s{2,}|\t|\s+(?=[B-Hb-h][.．、)）:：\s]|[【\[（(][B-Hb-h][】\]）]))|$)',
        re.DOTALL
    )
    matches = list(pattern.finditer(line))
    if len(matches) > 1:
        result = []
        for m in matches:
            key = (m.group(1) or m.group(2) or m.group(3)).upper()
            content = m.group(4).strip()
            result.append((key, content))
        return result
    return None


class TextExamParser:
    """Regex state machine parser for Markdown and plain text exam questions."""

    @classmethod
    def parse(cls, text: str) -> List[Dict[str, Any]]:
        """Parse raw text/markdown into standard question dictionaries."""
        if not text:
            return []

        # Normalize line breaks and remove BOM
        text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")

        questions: List[Dict[str, Any]] = []
        current_q: Optional[Dict[str, Any]] = None
        state = STATE_IDLE
        current_q_num = 0

        def finalize_question():
            nonlocal current_q
            if not current_q:
                return

            stem = current_q["stem"].strip()
            # If no answer yet, check if answer is embedded in stem: （ A ） or ( B )
            if not current_q["answer"]:
                emb = re.search(r'[（(\[]\s*([A-Ha-h对错TF正确错误]{1,8})\s*[）)\]]', stem)
                if emb:
                    current_q["answer"] = emb.group(1).strip()

            q_type, norm_ans = infer_type_and_answer(
                current_q.get("type", ""),
                current_q.get("answer", ""),
                current_q.get("options", []),
                stem
            )

            current_q["stem"] = stem
            current_q["type"] = q_type
            current_q["answer"] = norm_ans
            current_q["explanation"] = current_q["explanation"].strip()

            questions.append(current_q)
            current_q = None

        for raw_line in lines:
            line = raw_line.rstrip()
            stripped = line.strip()

            # Ignore empty lines unless we are in stem or explanation
            if not stripped:
                if state == STATE_STEM and current_q and current_q["stem"]:
                    current_q["stem"] += "\n"
                elif state == STATE_EXPLANATION and current_q and current_q["explanation"]:
                    current_q["explanation"] += "\n"
                continue

            # Strip leading markdown heading tokens for matching question starts
            heading_stripped = re.sub(r'^#{1,6}\s+', '', stripped)

            # 1. Check for Question Start
            q_match = Q_START_RE.match(heading_stripped)
            is_new_q = False
            matched_num = 0
            rest_of_stem = ""

            if q_match:
                matched_num_str = q_match.group(1) or q_match.group(2) or q_match.group(3) or q_match.group(4)
                matched_num = int(matched_num_str) if matched_num_str and matched_num_str.isdigit() else 0
                rest_of_stem = q_match.group(5).strip()

                # Guard against false positives (e.g. '100 米赛跑' in the middle of a stem)
                is_space_only_num = bool(q_match.group(4))
                if current_q is None:
                    is_new_q = True
                else:
                    has_completed_parts = bool(current_q["options"] or current_q["answer"] or current_q["explanation"])
                    if has_completed_parts:
                        is_new_q = True
                    elif not is_space_only_num:
                        # Has explicit punctuation like 2. or (2) or 【2】
                        is_new_q = True
                    elif matched_num == current_q_num + 1 or matched_num == 1:
                        is_new_q = True

            if is_new_q:
                finalize_question()
                current_q_num = matched_num
                current_q = {
                    "stem": rest_of_stem,
                    "type": "",
                    "options": [],
                    "answer": "",
                    "explanation": "",
                    "difficulty": 3,
                    "tags": [],
                }
                state = STATE_STEM
                continue

            # If no question active yet, skip preamble lines
            if current_q is None:
                continue

            # 2. Check for Answer Indicator
            ans_match = ANSWER_PREFIX_RE.match(stripped)
            if ans_match:
                ans_text = ans_match.group(1).strip()
                current_q["answer"] = ans_text
                state = STATE_ANSWER
                continue

            # 3. Check for Explanation Indicator
            exp_match = EXPLANATION_PREFIX_RE.match(stripped)
            if exp_match:
                exp_text = exp_match.group(1).strip()
                current_q["explanation"] = exp_text
                state = STATE_EXPLANATION
                continue

            # 4. Check for Difficulty Indicator
            diff_match = DIFFICULTY_PREFIX_RE.match(stripped)
            if diff_match:
                try:
                    current_q["difficulty"] = int(diff_match.group(1))
                except (ValueError, TypeError):
                    pass
                continue

            # 5. Check for Tags Indicator
            tags_match = TAGS_PREFIX_RE.match(stripped)
            if tags_match:
                raw_tags = tags_match.group(1).strip()
                if raw_tags:
                    tags = [t.strip() for t in re.split(r'[,，、;；\s]+', raw_tags) if t.strip()]
                    current_q["tags"].extend(tags)
                continue

            # 6. Check for Options
            # 6a. Single line with multiple options (e.g. 'A. 1 B. 2 C. 3 D. 4')
            inline_opts = _split_inline_options(stripped)
            if inline_opts and len(inline_opts) > 1:
                for opt_k, opt_v in inline_opts:
                    current_q["options"].append({"key": opt_k, "content": opt_v})
                state = STATE_OPTION
                continue

            # 6b. Single option at line start
            opt_match = OPT_START_RE.match(stripped)
            if opt_match and state != STATE_EXPLANATION:
                opt_key = (opt_match.group(1) or opt_match.group(2) or opt_match.group(3)).upper()
                opt_content = opt_match.group(4).strip()
                current_q["options"].append({"key": opt_key, "content": opt_content})
                state = STATE_OPTION
                continue

            # 7. State Continuation (Multiline accumulation)
            if state == STATE_STEM:
                if current_q["stem"]:
                    current_q["stem"] += "\n" + line
                else:
                    current_q["stem"] = line
            elif state == STATE_OPTION:
                if current_q["options"]:
                    current_q["options"][-1]["content"] += " " + stripped
            elif state == STATE_ANSWER:
                if not current_q["answer"]:
                    current_q["answer"] = stripped
                else:
                    current_q["answer"] += " " + stripped
            elif state == STATE_EXPLANATION:
                if current_q["explanation"]:
                    current_q["explanation"] += "\n" + stripped
                else:
                    current_q["explanation"] = stripped

        finalize_question()
        return questions


class CsvExamParser:
    """CSV parser with flexible Chinese column alias mapping and encoding tolerance."""

    STEM_ALIASES = {"题干", "题目", "stem", "question", "题干内容", "title", "content"}
    TYPE_ALIASES = {"题型", "type", "question_type", "类型"}
    ANSWER_ALIASES = {"答案", "answer", "正解", "正确答案", "key"}
    EXPLANATION_ALIASES = {"解析", "explanation", "分析", "答案解析", "analysis"}
    DIFFICULTY_ALIASES = {"难度", "difficulty", "level"}
    TAGS_ALIASES = {"标签", "tags", "tag", "知识点", "分类"}

    @classmethod
    def _find_column(cls, header_map: Dict[str, str], aliases: set) -> Optional[str]:
        for col_clean, orig_col in header_map.items():
            if col_clean in aliases:
                return orig_col
        return None

    @classmethod
    def parse(cls, csv_input: Union[str, bytes]) -> List[Dict[str, Any]]:
        """Parse CSV text or bytes into question dicts."""
        if not csv_input:
            return []

        # Decode if bytes
        if isinstance(csv_input, bytes):
            decoded = None
            for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
                try:
                    decoded = csv_input.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if decoded is None:
                decoded = csv_input.decode("utf-8", errors="replace")
            csv_text = decoded
        else:
            csv_text = csv_input.lstrip("\ufeff")

        reader = csv.DictReader(io.StringIO(csv_text))
        if not reader.fieldnames:
            return []

        # Map normalized header names to original header names
        header_map = {col.strip().lower(): col for col in reader.fieldnames if col}

        stem_col = cls._find_column(header_map, cls.STEM_ALIASES)
        type_col = cls._find_column(header_map, cls.TYPE_ALIASES)
        answer_col = cls._find_column(header_map, cls.ANSWER_ALIASES)
        exp_col = cls._find_column(header_map, cls.EXPLANATION_ALIASES)
        diff_col = cls._find_column(header_map, cls.DIFFICULTY_ALIASES)
        tags_col = cls._find_column(header_map, cls.TAGS_ALIASES)

        questions: List[Dict[str, Any]] = []

        for row in reader:
            stem = (row.get(stem_col) or "").strip() if stem_col else ""
            if not stem:
                continue

            raw_type = (row.get(type_col) or "").strip() if type_col else ""
            raw_answer = (row.get(answer_col) or "").strip() if answer_col else ""
            explanation = (row.get(exp_col) or "").strip() if exp_col else ""

            # Difficulty
            difficulty = 3
            if diff_col and row.get(diff_col):
                try:
                    difficulty = int(str(row.get(diff_col)).strip())
                except (ValueError, TypeError):
                    difficulty = 3

            # Tags
            tags = []
            if tags_col and row.get(tags_col):
                val = str(row.get(tags_col)).strip()
                if val:
                    tags = [t.strip() for t in re.split(r'[,，、;；\s]+', val) if t.strip()]

            # Extract options
            options: List[Dict[str, str]] = []

            # 1. Look for option columns: 'A', '选项A', 'option_a'
            for letter in "ABCDEFGH":
                possible_keys = {
                    letter.lower(),
                    f"选项{letter}".lower(),
                    f"选项 {letter}".lower(),
                    f"option_{letter}".lower(),
                    f"option {letter}".lower(),
                    f"option{letter}".lower()
                }
                opt_col = cls._find_column(header_map, possible_keys)
                if opt_col and row.get(opt_col):
                    content = str(row.get(opt_col)).strip()
                    if content:
                        options.append({"key": letter, "content": content})

            # 2. If no individual option columns, check single 'options' column
            if not options:
                opt_col = cls._find_column(header_map, {"options", "选项"})
                if opt_col and row.get(opt_col):
                    val = str(row.get(opt_col)).strip()
                    if val.startswith("[") and val.endswith("]"):
                        try:
                            parsed_opts = json.loads(val)
                            if isinstance(parsed_opts, list):
                                for item in parsed_opts:
                                    if isinstance(item, dict) and "key" in item and "content" in item:
                                        options.append({"key": item["key"], "content": item["content"]})
                        except json.JSONDecodeError:
                            pass
                    if not options:
                        # Fallback: extract using text parser logic
                        parsed_text = TextExamParser.parse(f"1. {stem}\n{val}\n【答案】{raw_answer}")
                        if parsed_text:
                            options = parsed_text[0].get("options", [])

            # Infer type and normalize answer
            q_type, norm_answer = infer_type_and_answer(raw_type, raw_answer, options, stem)

            questions.append({
                "stem": stem,
                "type": q_type,
                "options": options,
                "answer": norm_answer,
                "explanation": explanation,
                "difficulty": difficulty,
                "tags": tags,
            })

        return questions


class JsonExamParser:
    """JSON parser with schema validation and normalization."""

    @classmethod
    def parse(cls, json_text: str) -> List[Dict[str, Any]]:
        """Validate and parse a JSON string into a list of question dicts."""
        if not json_text or not json_text.strip():
            return []

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}") from e

        if isinstance(data, dict):
            if "questions" in data and isinstance(data["questions"], list):
                raw_list = data["questions"]
            elif "data" in data and isinstance(data["data"], list):
                raw_list = data["data"]
            elif "items" in data and isinstance(data["items"], list):
                raw_list = data["items"]
            elif "stem" in data:
                raw_list = [data]
            else:
                raise ValueError("Expected a JSON list of questions or an object with 'questions' key.")
        elif isinstance(data, list):
            raw_list = data
        else:
            raise ValueError("Invalid JSON structure: top-level must be a list or object.")

        questions: List[Dict[str, Any]] = []

        for idx, item in enumerate(raw_list):
            if not isinstance(item, dict):
                raise ValueError(f"Question at index {idx} must be a JSON object, got {type(item).__name__}.")

            stem = item.get("stem") or item.get("question") or item.get("题干")
            if not stem or not str(stem).strip():
                raise ValueError(f"Question at index {idx} is missing required 'stem' field.")
            stem = str(stem).strip()

            raw_type = str(item.get("type") or item.get("题型") or "").strip()
            raw_answer = str(item.get("answer") or item.get("答案") or "").strip()
            explanation = str(item.get("explanation") or item.get("解析") or item.get("analysis") or "").strip()

            try:
                difficulty = int(item.get("difficulty") or item.get("难度") or 3)
            except (ValueError, TypeError):
                difficulty = 3

            raw_tags = item.get("tags") or item.get("标签") or []
            if isinstance(raw_tags, str):
                tags = [t.strip() for t in re.split(r'[,，、;；\s]+', raw_tags) if t.strip()]
            elif isinstance(raw_tags, list):
                tags = [str(t).strip() for t in raw_tags if str(t).strip()]
            else:
                tags = []

            # Options
            options: List[Dict[str, str]] = []
            raw_options = item.get("options") or item.get("选项") or []
            if isinstance(raw_options, list):
                for opt in raw_options:
                    if isinstance(opt, dict) and "key" in opt and "content" in opt:
                        options.append({"key": str(opt["key"]).strip().upper(), "content": str(opt["content"]).strip()})
                    elif isinstance(opt, str):
                        # e.g. "A. xxx"
                        opt_match = OPT_START_RE.match(opt.strip())
                        if opt_match:
                            k = (opt_match.group(1) or opt_match.group(2) or opt_match.group(3)).upper()
                            c = opt_match.group(4).strip()
                            options.append({"key": k, "content": c})
            elif isinstance(raw_options, dict):
                for k, v in raw_options.items():
                    options.append({"key": str(k).strip().upper(), "content": str(v).strip()})

            q_type, norm_answer = infer_type_and_answer(raw_type, raw_answer, options, stem)

            questions.append({
                "stem": stem,
                "type": q_type,
                "options": options,
                "answer": norm_answer,
                "explanation": explanation,
                "difficulty": difficulty,
                "tags": tags,
            })

        return questions


# Functional aliases for convenience
def parse_markdown_text(text: str) -> List[Dict[str, Any]]:
    """Parse Markdown/text exam bank content."""
    return TextExamParser.parse(text)


def parse_csv_content(csv_input: Union[str, bytes]) -> List[Dict[str, Any]]:
    """Parse CSV exam bank content."""
    return CsvExamParser.parse(csv_input)


def parse_json_content(json_text: str) -> List[Dict[str, Any]]:
    """Parse JSON exam bank content."""
    return JsonExamParser.parse(json_text)
