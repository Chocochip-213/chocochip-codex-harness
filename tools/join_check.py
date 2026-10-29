#!/usr/bin/env python3
"""조인 점검: 두 표를 키로 합칠 때 행 수가 어떻게 바뀌는지 미리 본다.

사용:
  python3 join_check.py --left data/orders.csv:customer_id --right data/customers.csv:customer_id
  python3 join_check.py --left a.csv:order_id+line_no --right b.csv:order_id+line_no

보여 주는 것:
- 왼쪽·오른쪽 행 수와 고유 키 수, 오른쪽 키 중복(합치면 왼쪽 행이 불어남)
- 짝이 없는 왼쪽 행·오른쪽 키(그냥 합치면 조용히 빠짐)
- 키가 비거나 일부 빈 행(어느 쪽이든 조인에서 빠진다. 빈 키끼리는 맞추지 않는다)
- inner·left 조인 결과 행 수
- 공백·대소문자·기호를 지우고 맞추면 더 맞는 키(표기 흔들림)
개수는 전체를 세고 예시만 일부 보여 준다(--show 0이면 전부). 읽는 형식: .csv .tsv .json .jsonl
종료 코드: 0 점검함, 2 어느 쪽이든 행이 0개, 3 사용법·파일 오류.
"""
import argparse
import csv
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

import signal
if hasattr(signal, "SIGPIPE"):  # 출력을 head 등으로 자를 때 오류 없이 끝낸다
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

ENCODINGS = ("utf-8-sig", "cp949")
csv.field_size_limit(2**31 - 1)
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\d)(01[016789]|0\d{1,2})[-. ]?\d{3,4}[-. ]?\d{4}(?!\d)")
RRN = re.compile(r"(?<!\d)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])-?[1-8]\d{6}(?!\d)")  # 주민·외국인등록번호 모양


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(3)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        die(f"사용법 오류: {message}")


def read_text(path):
    raw = Path(path).read_bytes()
    for enc in ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


def split_spec(spec):
    if ":" not in spec:
        die(f"형식은 경로:열 입니다: {spec}")
    path, col = spec.rsplit(":", 1)
    return path, col.split("+")


ROW_LIST_NAMES = ("rows", "data", "items", "records", "results")


def pick_rows(data, path):
    """JSON 최상위가 객체면 그 안에서 '객체 목록'인 값을 고른다(행 목록 이름을 먼저, 없으면 처음 것)."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        die(f"{path}: 객체 목록이 아닙니다(최상위가 {type(data).__name__})")
    full = [(k, v) for k, v in data.items() if isinstance(v, list) and v and all(isinstance(x, dict) for x in v)]
    empty = [(k, v) for k, v in data.items() if isinstance(v, list) and not v]
    cands = full or empty
    if not cands:
        die(f"{path}: 객체 목록을 찾지 못했습니다(최상위 키: {', '.join(map(str, data)) or '없음'})")
    named = [c for c in cands if str(c[0]).lower() in ROW_LIST_NAMES]
    key, rows = (named or cands)[0]
    others = [str(k) for k, _ in cands if k != key]
    print(f"({Path(path).name}: JSON의 '{key}' 목록을 읽음" + (f", 다른 목록: {', '.join(others)})" if others else ")"))
    return rows


def records(path):
    """(열 이름 목록, dict 목록)"""
    p = Path(path)
    if not p.is_file():
        die(f"없는 파일: {path}")
    text = read_text(p)
    ext = p.suffix.lower()
    try:
        if ext in (".jsonl", ".ndjson"):
            recs = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
        elif ext == ".json":
            recs = pick_rows(json.loads(text), path)
        else:
            reader = csv.DictReader(io.StringIO(text, newline=""), delimiter="\t" if ext == ".tsv" else ",")
            recs = list(reader)
            return list(reader.fieldnames or []), recs
    except (json.JSONDecodeError, csv.Error) as e:
        die(f"{path}: 읽지 못했습니다({type(e).__name__}: {e})")
    recs = [r for r in recs if isinstance(r, dict)]
    names = []
    for r in recs:
        for k in r:
            if k not in names:
                names.append(k)
    return names, recs


def key_of(r, cols):
    return tuple("" if r.get(c) is None else str(r.get(c)).strip() for c in cols)


def is_empty(k):
    return any(x == "" for x in k)


def norm(k):
    return tuple(re.sub(r"[^0-9a-z가-힣]", "", unicodedata.normalize("NFKC", x).casefold()) for x in k)


def label(k):
    txt = "+".join(x if x != "" else "(빈 값)" for x in k)
    return PHONE.sub("<전화번호>", RRN.sub("<등록번호>", EMAIL.sub("<이메일>", txt)))


def show(items, n):
    items = list(items)
    shown = items if not n else items[:n]
    tail = f" 외 {len(items) - len(shown)}개" if len(shown) < len(items) else ""
    return ", ".join(shown) + tail


def main():
    ap = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--left", required=True, help="경로:열 (여러 열이면 열1+열2)")
    ap.add_argument("--right", required=True, help="경로:열")
    ap.add_argument("--show", type=int, default=5, help="예시 개수(0이면 전부)")
    a = ap.parse_args()

    lp, lc = split_spec(a.left)
    rp, rc = split_spec(a.right)
    if len(lc) != len(rc):
        die("왼쪽과 오른쪽 키 열 개수가 다릅니다")
    (lnames, left), (rnames, right) = records(lp), records(rp)
    for path, cols, names, rows in ((lp, lc, lnames, left), (rp, rc, rnames, right)):
        if not names and not rows:
            continue  # 빈 목록이라 열 정보가 없다. 아래에서 검사 0건으로 끝난다.
        missing = [c for c in cols if c not in names]
        if missing:
            die(f"{path}: 열이 없습니다: {missing}. 있는 열: {names}")
    print(f"왼쪽 {lp}: 행 {len(left)}개 / 오른쪽 {rp}: 행 {len(right)}개")
    if not left or not right:
        print("검사 0건: 한쪽이 비어 있습니다.")
        return 2

    rkeys = [key_of(r, rc) for r in right]
    lkeys = [key_of(r, lc) for r in left]
    r_empty = sum(1 for k in rkeys if is_empty(k))
    l_empty = sum(1 for k in lkeys if is_empty(k))
    rcount = {}
    for k in rkeys:
        if not is_empty(k):
            rcount[k] = rcount.get(k, 0) + 1
    lfilled = [k for k in lkeys if not is_empty(k)]
    lset = set(lfilled)
    dup = {k: n for k, n in rcount.items() if n > 1}
    matched = [k for k in lfilled if k in rcount]
    unmatched_left = [k for k in lfilled if k not in rcount]
    unmatched_right = [k for k in rcount if k not in lset]
    inner = sum(rcount[k] for k in matched)
    left_join = inner + len(unmatched_left) + l_empty

    print(f"- 고유 키: 왼쪽 {len(lset)}개, 오른쪽 {len(rcount)}개")
    if l_empty or r_empty:
        print(f"- 키가 비거나 일부 빈 행: 왼쪽 {l_empty}개, 오른쪽 {r_empty}개(조인에서 짝을 찾지 않는다)")
    if dup:
        extra = sum(rcount[k] - 1 for k in matched if k in dup)
        print(f"- 오른쪽 키 중복 {len(dup)}개(합치면 왼쪽 행이 {extra}개 불어남): " +
              show((f"{label(k)}×{n}" for k, n in sorted(dup.items())), a.show))
    print(f"- 짝이 있는 왼쪽 행 {len(matched)}개, 짝이 없는 왼쪽 행 {len(unmatched_left)}개(키가 빈 행 제외)")
    if unmatched_left:
        print("    짝이 없는 왼쪽 키: " + show((label(k) for k in sorted(set(unmatched_left))), a.show))
    if unmatched_right:
        print(f"- 왼쪽에 없는 오른쪽 키 {len(unmatched_right)}개: " +
              show((label(k) for k in sorted(unmatched_right)), a.show))
    print(f"- 조인 결과 행 수: inner {inner}개, left {left_join}개 (왼쪽 {len(left)}개 기준)")

    rnorm = {}
    for k in rcount:
        nk = norm(k)
        if all(nk):
            rnorm.setdefault(nk, []).append(k)
    rescued = sorted({k for k in unmatched_left if all(norm(k)) and norm(k) in rnorm})
    if rescued:
        pairs = [f"{label(k)}→{label(rnorm[norm(k)][0])}" for k in rescued]
        print(f"- 공백·대소문자·기호를 지우면 더 맞는 왼쪽 키 {len(rescued)}개(표기 흔들림): " + show(pairs, a.show))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(3)
    except Exception as e:  # 예상 못 한 오류는 3으로 끝낸다
        print(f"실행 오류: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(3)
