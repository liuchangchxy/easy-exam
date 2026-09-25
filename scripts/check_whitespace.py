import os
import subprocess
import sys

def main():
    res = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    paths = []
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        p = line[3:].strip()
        if p.startswith('"') and p.endswith('"'):
            p = p[1:-1]
        paths.append(p)

    errors = 0
    checked_count = 0
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, fnames in os.walk(p):
                for fname in fnames:
                    full = os.path.join(root, fname)
                    if any(x in full for x in ["node_modules", ".git", "__pycache__", "dist", ".pytest_cache"]):
                        continue
                    errors += check_file(full)
                    checked_count += 1
        elif os.path.isfile(p):
            errors += check_file(p)
            checked_count += 1

    print(f"Checked {checked_count} modified/untracked files. Total whitespace/EOF errors: {errors}")
    if errors > 0:
        sys.exit(1)

def check_file(file_path):
    errs = 0
    try:
        with open(file_path, "rb") as fp:
            data = fp.read()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return 0
        lines = text.splitlines(keepends=True)
        for idx, l in enumerate(lines, 1):
            s = l.rstrip("\r\n")
            if s != s.rstrip(" \t"):
                print(f"Trailing whitespace in {file_path}:{idx}")
                errs += 1
        if text and not text.endswith("\n"):
            print(f"Missing EOF newline in {file_path}")
            errs += 1
    except Exception as ex:
        print(f"Failed to check {file_path}: {ex}")
    return errs

if __name__ == "__main__":
    main()
