#!/usr/bin/env python3
"""제출 전 점검: 키 모양, 할 일 표시(TODO·FIXME), 개인정보 모양을 찾는다.

사용: 작업 폴더 맨 위에서 python3 .harness/tools/precheck.py [--exclude 폴더나 파일 ...] [--show-data] [--include-ignored]
- git이 아는 파일(커밋된 것과 새 파일)을 본다. git이 아니면 폴더 전체.
- .gitignore에 걸린 것은 검사하지 않고 이름을 보인다. 제출이 폴더 통째라면 --include-ignored로 함께 검사한다.
- .harness/ .agents/ 는 하네스 파일이라 뺀다. 입력 데이터 폴더는 --exclude로 뺄 수 있다.
- 데이터 파일(csv·tsv·json·jsonl)의 개인정보 모양은 입력에 원래 있던 값일 수 있어 파일별 줄 수만 보인다.
  줄까지 보려면 --show-data. 키 모양·할 일 표시는 데이터 파일에서도 줄까지 보인다.
- 제출 문서의 /tmp 인용: 하네스 설치 뒤 바뀐 .md(verify/·AGENTS.md 제외)에서 /tmp를 말하는 줄. 근거로 든 스크립트면
  verify/로 옮기거나 문장을 고친다. 행 목록 같은 자료 사본 경로면 남겨도 된다.
- 남은 검증 차이: verify/의 report·diff 번호 중 가장 큰 N의 diff_N.csv에 차이 줄이 있으면. 고쳤으면 verify 비교를
  다시 해 diff·report를 지금 값으로 갱신한다. 고치지 않았으면 남긴 이유를 적는다.
- 열지 못한 파일(권한 등)도 찾은 것으로 센다. 지워진 파일은 건너뛴다.
- 찾은 값은 가려서 보인다(전체 값을 화면과 로그에 내지 않는다). 맨 앞 줄에 종류별 건수를 먼저 보인다.
- 종료 코드: 0 찾은 것 없음, 1 찾은 것 있음, 3 실행 오류.
"""
import argparse
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

if hasattr(signal, "SIGPIPE"):
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

ALWAYS_SKIP = (".harness/", ".agents/", ".git/")
WALK_SKIP_DIRS = {".git", ".harness", ".agents", "node_modules", ".venv", "venv", "__pycache__",
                  ".mypy_cache", ".pytest_cache", ".ruff_cache"}
DATA_EXT = {".csv", ".tsv", ".json", ".jsonl", ".ndjson"}

SECRET_NAME = r"(api[_-]?key|access[_-]?key|private[_-]?key|secret(?:[_-]?key)?|password|passwd|token)"
KEY_PATTERNS = [
    re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?<![A-Za-z0-9])AKIA[0-9A-Z]{16}"),
    re.compile(r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    # 따옴표 안의 값을 넣는 대입: api_key = "...", "password": "..."
    re.compile(r"(?i)" + SECRET_NAME + r"[\"']?\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']"),
    # .env 모양: OPENAI_API_KEY=abcd1234, export db_password=... (이름이 키 이름으로 끝날 때만. 값이 함수 호출·인덱싱·${변수}면 제외)
    re.compile(r"(?i)^\s*(export\s+)?[A-Z0-9_]*" + SECRET_NAME + r"\s*=\s*[\"']?[^\s#(\[\"'$]{8,}[\"']?\s*(#.*)?$"),
    # YAML 모양: token: abcd1234
    re.compile(r"(?i)^\s*[\w.-]*" + SECRET_NAME + r"\s*:\s*[^\s#(\[\"'$]{8,}\s*$"),
]
EMAIL = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
MOBILE = r"(?<![\d+])(\+82[-. ]?|0)1[016789][-. ]?\d{3,4}[-. ]?\d{4}(?!\d)"
LANDLINE = r"(?<![\d+])(\+82[-. ]?|0)(2|3[1-3]|4[1-4]|5[1-5]|6[1-4]|70|50\d)[-. ]?\d{3,4}[-. ]?\d{4}(?!\d)"
RRN = r"(?<!\d)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])-?[1-8]\d{6}(?!\d)"
CATEGORIES = [
    ("key", "키 모양", KEY_PATTERNS),
    ("todo", "할 일 표시(TODO·FIXME)", [re.compile(r"\b(TODO|FIXME)\b")]),
    ("email", "이메일", [re.compile(EMAIL)]),
    ("phone", "휴대전화번호", [re.compile(MOBILE)]),
    ("landline", "유선·인터넷 전화번호 모양", [re.compile(LANDLINE)]),
    ("rrn", "주민·외국인등록번호 모양", [re.compile(RRN)]),
]
PII = {"email", "phone", "landline", "rrn"}
TMP_REF = re.compile(r"(?<![\w.])/tmp(?![\w-])")
DIFF_NAME = re.compile(r"^verify/diff_(\d+)\.csv$")
REPORT_NAME = re.compile(r"^verify/report_(\d+)\.md$")
FILE_CHECKS = [("tmp", "제출 문서의 /tmp 인용"), ("diff", "남은 검증 차이"), ("unread", "열지 못한 파일")]
MASKS = [
    (re.compile(EMAIL), "<이메일>"),
    (re.compile(RRN), "<등록번호>"),
    (re.compile(MOBILE), "<전화번호>"),
    (re.compile(LANDLINE), "<전화번호>"),
]
LINE_SHOW = 200


def mask_secret(chunk):
    """대입문이면 = 또는 : 뒤의 값만(Bearer는 뒤의 값만), 아니면 전체를 앞 4자만 남기고 가린다."""
    m = None if chunk.startswith("-----") else re.search(r"[:=]\s*|(?i:bearer)\s+", chunk)
    head, value = (chunk[:m.end()], chunk[m.end():]) if m and m.end() < len(chunk) else ("", chunk)
    q = value[:1] if value[:1] in ("'", '"') else ""
    core = value[len(q):]
    if q and core.endswith(q):
        core = core[:-1]
    return head + q + core[:4] + "…(가림)" + q


def mask_line(line, key_spans):
    """개인정보는 종류 이름으로, 키 모양 값은 앞 4자만 남기고 가린다."""
    out = line
    merged = []
    for start, end in sorted(key_spans):
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    for start, end in reversed(merged):
        out = out[:start] + mask_secret(out[start:end]) + out[end:]
    for pat, label in MASKS:
        out = pat.sub(label, out)
    out = out.strip()
    if len(out) > LINE_SHOW:
        out = out[:LINE_SHOW] + f"…(줄 길이 {len(out)}자)"
    return out


def git_list(args):
    p = subprocess.run(["git", "ls-files", "-z"] + args, capture_output=True, timeout=30)
    if p.returncode != 0:
        raise OSError(p.stderr.decode("utf-8", "replace").strip())
    return [n for n in p.stdout.decode("utf-8", "replace").split("\0") if n]


def walk(top="."):
    names = []
    for root, dirs, files in os.walk(top):
        dirs[:] = [d for d in dirs if d not in WALK_SKIP_DIRS]
        for f in files:
            names.append(os.path.relpath(os.path.join(root, f), "."))
    return names


def is_heavy_dir(entry):
    return entry.endswith("/") and Path(entry.rstrip("/")).name in WALK_SKIP_DIRS


def list_files(excludes, include_ignored):
    ignored = []
    try:
        names = git_list(["-co", "--exclude-standard"])
        source = "git이 아는 파일(커밋된 것과 새 파일)"
        ignored = git_list(["-oi", "--exclude-standard", "--directory"])
        if include_ignored:
            for ig in ignored:
                if ig.endswith("/"):
                    if not is_heavy_dir(ig):
                        names.extend(walk(ig))
                else:
                    names.append(ig)
            source += "과 .gitignore에 걸린 파일(--include-ignored, 라이브러리·캐시 폴더 제외)"
            ignored = [ig for ig in ignored if is_heavy_dir(ig)]
    except (OSError, subprocess.TimeoutExpired):
        names = walk()
        source = "폴더 전체(git 저장소가 아님. node_modules·.venv·캐시 폴더 제외)"
    norm_ex = []
    for e in excludes:
        e = os.path.normpath(os.path.relpath(e) if os.path.isabs(e) else e).replace(os.sep, "/")
        if e != ".":
            norm_ex.append(e)
    kept, skipped_ex = [], 0
    for n in sorted(set(names)):
        n = n.replace(os.sep, "/")
        if n.startswith("./"):
            n = n[2:]
        if n.startswith(ALWAYS_SKIP):
            continue
        if any(n == e or n.startswith(e + "/") for e in norm_ex):
            skipped_ex += 1
            continue
        kept.append(n)
    ignored = [ig for ig in ignored if not ig.startswith(ALWAYS_SKIP)]
    return kept, source, skipped_ex, ignored


def key_spans(line):
    return [m.span() for pat in KEY_PATTERNS for m in pat.finditer(line)]


def changed_md(files):
    """하네스 설치(.harness/BASE) 뒤 바뀌었거나 git이 추적하지 않는 .md. BASE가 없거나 git이 아니면 .md 전부."""
    md = [n for n in files if n.lower().endswith(".md") and not n.startswith("verify/") and n != "AGENTS.md"]
    base = Path(".harness/BASE")
    b = base.read_text(encoding="utf-8", errors="replace").strip() if base.is_file() else ""
    if not b:
        return md
    try:
        p = subprocess.run(["git", "diff", "--name-only", "-z", b], capture_output=True, timeout=30)
        if p.returncode != 0:
            return md
        changed = {n for n in p.stdout.decode("utf-8", "replace").split("\0") if n}
        tracked = set(git_list(["-c"]))
    except (OSError, subprocess.TimeoutExpired):
        return md
    return [n for n in md if n in changed or n not in tracked]


def file_checks(files):
    """줄 하나가 아니라 파일 묶음을 봐야 하는 점검(/tmp 인용, 남은 검증 차이)"""
    out = {"tmp": [], "diff": []}
    for name in changed_md(files):
        try:
            text = Path(name).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # 못 읽은 파일은 본 점검에서 '열지 못한 파일'로 센다
        for lineno, line in enumerate(text.splitlines(), 1):
            if TMP_REF.search(line):
                out["tmp"].append(f"{name}:{lineno}  {mask_line(line, key_spans(line))}")
    diffs = {int(m.group(1)): n for n in files for m in [DIFF_NAME.match(n)] if m}
    nums = set(diffs) | {int(m.group(1)) for n in files for m in [REPORT_NAME.match(n)] if m}
    if nums and max(nums) in diffs:
        name = diffs[max(nums)]
        try:
            rows = [ln for ln in Path(name).read_text(encoding="utf-8", errors="replace").splitlines()[1:] if ln.strip()]
        except OSError:
            rows = []
        if rows:
            out["diff"].append(f"{name}: 차이 {len(rows)}줄")
    return out


FILE_GUIDE = {
    "tmp": "근거로 든 스크립트면 verify/로 옮기거나 문장을 고친다. 행 목록 같은 자료 사본 경로면 남겨도 된다",
    "diff": "고쳤으면 verify 비교를 다시 해 diff·report를 지금 값으로 갱신한다. 고치지 않았으면 남긴 이유를 적는다",
    "unread": "검사하지 못했다. 권한을 확인하거나 남긴 이유를 적는다",
}


class Parser(argparse.ArgumentParser):
    def error(self, message):  # 사용법 오류도 실행 오류(3)로 구분한다
        self.print_usage(sys.stderr)
        print(f"사용법 오류: {message}", file=sys.stderr)
        sys.exit(3)


def main():
    ap = Parser(description="제출 전 점검: 키·할 일 표시·개인정보 모양")
    ap.add_argument("--exclude", nargs="*", default=[], help="뺄 폴더나 파일(입력 데이터 폴더 등)")
    ap.add_argument("--show-data", action="store_true", help="데이터 파일의 개인정보 모양도 줄까지 보인다")
    ap.add_argument("--include-ignored", action="store_true", help=".gitignore에 걸린 파일도 검사한다")
    a = ap.parse_args()

    files, source, skipped_ex, ignored = list_files(a.exclude, a.include_ignored)
    found = {key: [] for key, _, _ in CATEGORIES}
    data_counts = {}
    binary = []
    found["unread"] = []
    for name in files:
        path = Path(name)
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except FileNotFoundError:
            continue  # git 목록에는 있지만 지워진 파일
        except OSError as e:
            found["unread"].append(f"{name}({type(e).__name__})")
            continue
        if b"\0" in raw[:8192]:
            binary.append(name)
            continue
        text = raw.decode("utf-8", "replace")
        is_data = path.suffix.lower() in DATA_EXT
        for lineno, line in enumerate(text.splitlines(), 1):
            spans = key_spans(line)
            for key, _, pats in CATEGORIES:
                if not (spans if key == "key" else any(p.search(line) for p in pats)):
                    continue
                if key in PII and is_data and not a.show_data:
                    data_counts.setdefault(name, {}).setdefault(key, 0)
                    data_counts[name][key] += 1
                    continue
                found[key].append(f"{name}:{lineno}  {mask_line(line, spans)}")

    found.update(file_checks(files))
    labels = {key: label for key, label, _ in CATEGORIES}
    labels.update(FILE_CHECKS)
    order = [key for key, _, _ in CATEGORIES] + [key for key, _ in FILE_CHECKS]
    dsum = sum(sum(c.values()) for c in data_counts.values())
    total = sum(len(v) for v in found.values()) + dsum
    summary = ", ".join(f"{labels[k]} {len(found[k])}" for k in order)
    print(f"결과: 찾은 것 {total}건 ({summary}, 데이터 파일의 개인정보 모양 {dsum}줄)"
          + (" → 각각 지우거나 남기는 이유를 적는다" if total else ""))
    excl = ", ".join(a.exclude) if a.exclude else "없음"
    print(f"점검한 파일 {len(files)}개: {source}. 늘 빼는 것: .harness/ .agents/. --exclude: {excl}"
          + (f"(뺀 파일 {skipped_ex}개)" if a.exclude else ""))
    if ignored:
        print(f"검사하지 않은 것(.gitignore에 걸림) {len(ignored)}개: " + ", ".join(ignored)
              + ("" if a.include_ignored else ". 제출이 폴더 통째라면 --include-ignored로 함께 검사한다"))
    if binary:
        print(f"읽지 않은 파일(이진 파일) {len(binary)}개: " + ", ".join(binary))
    for key in order:
        if found[key]:
            print(f"[{labels[key]}] {len(found[key])}건" + (f" → {FILE_GUIDE[key]}" if key in FILE_GUIDE else ""))
            for r in found[key]:
                print("  " + r)
    if data_counts:
        print(f"[데이터 파일의 개인정보 모양] {dsum}줄. 입력 데이터에 원래 있던 값일 수 있어 파일별 줄 수만 보인다(줄까지는 --show-data):")
        for name in sorted(data_counts):
            parts = ", ".join(f"{labels[k]} {v}줄" for k, v in data_counts[name].items())
            print(f"  {name}: {parts}")
    return 1 if total else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(3)
    except Exception as e:  # 도구 자체 오류는 3으로 구분한다
        print(f"실행 오류: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(3)
