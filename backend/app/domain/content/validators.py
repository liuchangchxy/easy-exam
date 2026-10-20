import re
from typing import Any, Dict, List, Set, Tuple


def normalize_answer_keys(raw_answer: str) -> List[str]:
    """Extract ordered unique answer keys from a raw answer string."""
    if not raw_answer:
        return []
    clean = str(raw_answer).strip()
    if not clean:
        return []
    # If separated by commas, semicolons, or whitespace
    parts = re.split(r"[,;\s]+", clean)
    keys = []
    for p in parts:
        p_clean = p.strip()
        if not p_clean:
            continue
        # If part is something like "AB", split into single chars if letters
        if len(p_clean) > 1 and p_clean.isalpha() and p_clean.isupper():
            keys.extend(list(p_clean))
        else:
            keys.append(p_clean)
    # Deduplicate while preserving deterministic sorted order
    seen: Set[str] = set()
    result = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            result.append(k)
    return result


def validate_question_invariants(
    q_type: str,
    stem: str,
    options: List[Dict[str, Any]],
    answer: str,
) -> Tuple[str, str, List[Dict[str, Any]]]:
    """
    Validate and normalize question type, stem, options, and answer invariants.
    Returns (normalized_type, normalized_answer, normalized_options).
    Raises ValueError on validation failure.
    """
    stem_clean = str(stem or "").strip()
    if not stem_clean:
        raise ValueError("题干不能为空")

    norm_type = str(q_type or "SINGLE").strip().upper()
    if norm_type not in {"SINGLE", "MULTI", "JUDGE", "FILL", "ESSAY", "QA", "SHORT_ANSWER", "SUBJECTIVE"}:
        raise ValueError(f"不支持的题型: {norm_type}")

    raw_options = options if isinstance(options, list) else []
    option_keys: List[str] = []
    clean_options: List[Dict[str, Any]] = []
    for opt in raw_options:
        if not isinstance(opt, dict):
            continue
        opt_copy = dict(opt)
        if "content" not in opt_copy and "text" in opt_copy:
            opt_copy["content"] = opt_copy["text"]
        elif "text" not in opt_copy and "content" in opt_copy:
            opt_copy["text"] = opt_copy["content"]
        key = str(opt_copy.get("key") or "").strip()
        if key:
            if key in option_keys:
                raise ValueError(f"选项键 '{key}' 重复，选项键必须唯一")
            option_keys.append(key)
        clean_options.append(opt_copy)

    valid_keys_set = set(option_keys)

    if norm_type == "MULTI":
        if len(option_keys) < 2:
            raise ValueError("多选题必须至少包含2个选项")
        ans_keys = normalize_answer_keys(answer)
        if len(ans_keys) < 2:
            raise ValueError("多选题必须至少包含两个不同的正确答案选项")
        resolved_keys = []
        for k in ans_keys:
            if k in valid_keys_set:
                resolved_keys.append(k)
            else:
                found = False
                for opt in clean_options:
                    text_val = str(opt.get("content") or opt.get("text") or "").strip()
                    if text_val == k:
                        resolved_keys.append(opt["key"])
                        found = True
                        break
                if not found:
                    raise ValueError(f"多选题答案包含不存在的选项键 '{k}'，合法选项: {option_keys}")
        if len(set(resolved_keys)) < 2:
            raise ValueError("多选题必须至少包含两个不同的正确答案选项")
        norm_ans = ",".join(sorted(set(resolved_keys)))
        return norm_type, norm_ans, clean_options

    if norm_type == "SINGLE":
        if len(option_keys) < 2:
            raise ValueError("单选题必须至少包含2个选项")
        clean_ans = str(answer or "").strip()
        if not clean_ans:
            raise ValueError("单选题答案不能为空")
        ans_keys = normalize_answer_keys(clean_ans)
        if len(ans_keys) != 1:
            raise ValueError("单选题必须恰好有一个正确答案")
        single_key = ans_keys[0]
        if single_key not in valid_keys_set:
            for opt in clean_options:
                text_val = str(opt.get("content") or opt.get("text") or "").strip()
                if text_val == clean_ans:
                    single_key = opt["key"]
                    break
        if single_key not in valid_keys_set:
            raise ValueError(f"单选题答案包含不存在的选项键 '{single_key}'，合法选项: {option_keys}")
        return norm_type, single_key, clean_options

    if norm_type == "JUDGE":
        clean_raw = str(answer or "").strip().upper()
        if clean_raw in {"T", "TRUE", "1", "对", "正确"}:
            clean_ans = "T"
        elif clean_raw in {"F", "FALSE", "0", "错", "错误"}:
            clean_ans = "F"
        else:
            raise ValueError(f"判断题答案必须为正确(T)或错误(F)，当前为 '{answer}'")
        judge_options = [
            {"key": "T", "content": "正确"},
            {"key": "F", "content": "错误"},
        ]
        return norm_type, clean_ans, judge_options

    # FILL or ESSAY or other subjective types
    clean_ans = str(answer or "").strip()
    return norm_type, clean_ans, clean_options
