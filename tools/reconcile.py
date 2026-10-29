#!/usr/bin/env python3
"""행 대조: 들어온 행이 결과 쪽(쓴 것, 뺀 것, 따로 둔 것)에 행 단위로 빠짐없이, 넘치지 않게 나뉘었는지 ID로 확인한다.

사용:
  # 결과가 파일 여러 개일 때
  python3 reconcile.py --input data/input.csv:id \\
      --part 쓴=out/kept.csv --part 뺀=out/dropped.csv --part 따로=out/review.csv

  # 결과가 파일 하나이고 구분 열(예: status)로 나뉠 때(결과 JSON의 rows 목록도 읽는다)
  python3 reconcile.py --input data/input.csv:id --group out/result.json:id:판정

  # 여러 행을 하나로 묶어 ID를 한 칸에 적었을 때(예: "A1;A7;A9")
  python3 reconcile.py --input data/input.csv:id --part 묶음=out/groups.csv:member_ids --sep ';'

- ID마다 '들어온 행 수 = 결과 쪽 행 수의 합'인지 본다. 같은 ID가 입력에 두 행이면 결과 쪽에도 두 행
  (예: 쓴 1 + 뺀 1)이어야 한다. 중복을 지웠다면 지운 행은 '뺀' 쪽에 적어야 맞는다.
- 경로:열 에서 열 이름이 여럿이면 col1+col2 로 쓴다. --part의 열을 생략하면 --input과 같은 열을 쓴다.
- 읽는 형식: .csv .tsv .json(객체 목록, 또는 객체 목록을 값으로 가진 객체) .jsonl, 그리고 ID만 한 줄에 하나씩 적은 .txt
- 종료 코드: 0 일치, 1 불일치, 2 검사 0건(입력이나 결과 쪽에서 ID를 하나도 못 읽음), 3 사용법·파일 오류.
- 차이는 메우지 말고 '원인 미상 n건'으로 남긴다. 개수는 전체를 세고 예시만 일부 보여 준다(--show 0이면 전부).

보고:
- 대조할 행 목록은 /tmp에 따로 만들고, 요구에 없으면 제출 결과 파일에 넣지 않는다.
- 출력 첫 줄은 '요약:'(종료 코드와 행 수)이다. 단계 보고에는 이 줄만 붙이고, 안 맞을 때만 그 아래 내용을 알린다.
"""
import argparse
import csv
import io
import json
import re
import sys
from collections import Counter
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
    print(f"요약: 종료 3, 실행 오류: {msg}")
    print(msg, file=sys.stderr)
    sys.exit(3)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        die(f"사용법 오류: {message}")


def mask(v):
    return PHONE.sub("<전화번호>", RRN.sub("<등록번호>", EMAIL.sub("<이메일>", str(v))))


def read_text(path):
    raw = Path(path).read_bytes()
    for enc in ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


def split_spec(spec, parts):
    """'경로:열' 또는 '경로:열:구분열'을 나눈다. 열이 없으면 None."""
    bits = spec.split(":")
    if len(bits) < parts:
        return [spec] + [None] * (parts - 1)
    path = ":".join(bits[: len(bits) - (parts - 1)])
    return [path] + bits[len(bits) - (parts - 1):]


ROW_LIST_NAMES = ("rows", "data", "items", "records", "results")
NOTES = []  # 읽으면서 알릴 말. 요약 줄 다음에 찍는다
PICKED = []  # JSON에서 고른 행 목록 이름. 요약 줄 끝에 붙인다
SEP = "\x1f"  # 여러 열을 합친 키의 구분자(값 안의 '|'와 섞이지 않게). 보일 때만 '|'로 바꾼다


def pick_rows(data, path):
    """JSON 최상위가 객체면 그 안에서 '객체 목록'인 값을 고른다(행 목록 이름을 먼저, 없으면 처음 것)."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        die(f"{path}: 객체 목록이 아닙니다(최상위가 {type(data).__name__})")
    cands = [(k, v) for k, v in data.items() if isinstance(v, list) and (not v or any(isinstance(x, dict) for x in v))]
    if not cands:
        die(f"{path}: 객체 목록을 찾지 못했습니다(최상위 키: {', '.join(map(str, data)) or '없음'})")
    named = sorted((c for c in cands if str(c[0]).lower() in ROW_LIST_NAMES),
                   key=lambda c: ROW_LIST_NAMES.index(str(c[0]).lower()))
    nonempty = [c for c in cands if c[1]]
    if named:
        key, rows = named[0]
    elif len(nonempty) > 1:
        die(f"{path}: 어느 목록이 행인지 정할 수 없습니다(객체 목록: {', '.join(str(k) for k, _ in nonempty)}). "
            "행 목록을 rows로 이름 붙이거나 그 목록만 따로 저장한다")
    else:
        key, rows = (nonempty or cands)[0]
    others = [str(k) for k, _ in cands if k != key]
    PICKED.append(f"{Path(path).name}: '{key}'")
    NOTES.append(f"({Path(path).name}: JSON의 '{key}' 목록을 읽음" + (f", 다른 목록: {', '.join(others)})" if others else ")"))
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
    bad = sum(1 for r in recs if not isinstance(r, dict))
    if bad:
        die(f"{path}: 행 목록에 객체가 아닌 항목 {bad}개(행이 조용히 빠질 수 있어 멈춤)")
    names = []
    for r in recs:
        for k in r:
            if k not in names:
                names.append(k)
    return names, recs


def cell(r, cols):
    vals = []
    for c in cols:
        v = r.get(c)
        if isinstance(v, (list, tuple)):
            v = ";".join(str(x) for x in v)
        vals.append("" if v is None else str(v).strip())
    return SEP.join(vals)


def keys_of(path, key, sep=None):
    """ID 목록(행마다 하나, 한 칸에 여럿이면 각각)과 ID가 빈 행 수"""
    if Path(path).suffix.lower() == ".txt" or key is None:
        if not Path(path).is_file():
            die(f"없는 파일: {path}")
        return [ln.strip() for ln in read_text(path).splitlines() if ln.strip()], 0
    names, recs = records(path)
    cols = key.split("+")
    missing = [c for c in cols if c not in names]
    if missing and (names or recs):  # 열 이름도 행도 없으면(빈 목록) 검사 0건으로 넘긴다
        die(f"{path}: 열이 없습니다: {missing}. 있는 열: {names}")
    ids, empty = [], 0
    for r in recs:
        v = cell(r, cols)
        parts = [x.strip() for x in v.split(sep)] if sep else [v]
        for x in parts:
            if x.replace(SEP, "") == "":
                empty += 1
            else:
                ids.append(x)
    return ids, empty


def main():
    ap = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="입력경로:ID열")
    ap.add_argument("--part", action="append", default=[], help="이름=경로[:ID열]")
    ap.add_argument("--group", action="append", default=[], help="경로:ID열:구분열")
    ap.add_argument("--sep", help="한 칸에 ID가 여러 개일 때 구분자(--part에만 적용)")
    ap.add_argument("--show", type=int, default=10, help="예시 개수(0이면 전부)")
    a = ap.parse_args()
    if not a.part and not a.group:
        ap.error("--part나 --group이 하나 이상 필요합니다")
    lim = a.show if a.show and a.show > 0 else None

    def ex(seq):
        seq = list(seq)
        shown = seq[:lim] if lim else seq
        tail = f" 외 {len(seq) - len(shown)}개(전부 보려면 --show 0)" if len(shown) < len(seq) else ""
        return ", ".join(mask(str(x).replace(SEP, "|")) for x in shown) + tail

    in_path, in_key = split_spec(a.input, 2)
    if in_key is None:
        ap.error("--input에는 ID 열이 필요합니다: 경로:열")
    inp, in_empty = keys_of(in_path, in_key)

    parts = []  # (이름, ID 목록, ID가 빈 행 수)
    for spec in a.part:
        if "=" not in spec:
            ap.error(f"--part 형식은 이름=경로[:열] 입니다: {spec}")
        name, rest = spec.split("=", 1)
        p, k = split_spec(rest, 2)
        ids, empty = keys_of(p, k or in_key, a.sep)
        parts.append((name, ids, empty))
    for spec in a.group:
        p, k, g = split_spec(spec, 3)
        if not k or not g:
            ap.error(f"--group 형식은 경로:ID열:구분열 입니다: {spec}")
        names, recs = records(p)
        for c in k.split("+") + [g]:
            if (names or recs) and c not in names:
                die(f"{p}: 열이 없습니다: {c}. 있는 열: {names}")
        buckets = {}
        for r in recs:
            label = str(r.get(g) if r.get(g) is not None else "").strip() or "(구분 없음)"
            ids, empty = buckets.setdefault(label, ([], [0]))
            v = cell(r, k.split("+"))
            if v.replace(SEP, "") == "":
                empty[0] += 1
            else:
                ids.append(v)
        for label, (ids, empty) in buckets.items():
            parts.append((f"{g}={label}", ids, empty[0]))

    if not inp or not any(ids for _, ids, _ in parts):
        print("요약: 종료 2, 검사 0건(통과 아님)")
        for n in NOTES:
            print(n)
        if not inp:
            print(f"검사 0건: 입력 {in_path}에서 ID를 하나도 읽지 못했습니다(ID가 빈 행 {in_empty}개). 통과가 아닙니다.")
        else:
            print("검사 0건: 결과 쪽 파일에서 ID를 하나도 읽지 못했습니다. 통과가 아닙니다.")
        return 2

    cin = Counter(inp)
    cparts = [(n, Counter(ids)) for n, ids, _ in parts]
    cout = Counter()
    for _, c in cparts:
        cout.update(c)
    out_rows = sum(len(ids) for _, ids, _ in parts)
    out_empty = sum(e for _, _, e in parts)

    lost, short, extra, more = [], [], [], []
    for x in sorted(set(cin) | set(cout)):
        i, o = cin.get(x, 0), cout.get(x, 0)
        if i == o:
            continue
        where = "·".join(f"{n}{c[x]}" for n, c in cparts if c.get(x))
        if o == 0:
            lost.append(f"{x}(입력 {i}행)")
        elif i == 0:
            extra.append(f"{x}({where})")
        elif o < i:
            short.append(f"{x}(입력 {i}행, 결과 {o}행: {where})")
        else:
            more.append(f"{x}(입력 {i}행, 결과 {o}행: {where})")
    empty_bad = in_empty != out_empty
    in_rows = len(inp) + in_empty
    parts_str = " + ".join(f"{n} {len(ids)}" for n, ids, _ in parts) + (f" + ID가 빈 행 {out_empty}" if out_empty else "")
    n_bad = len(lost) + len(short) + len(extra) + len(more) + (1 if empty_bad else 0)
    picked = f" ({', '.join(PICKED)})" if PICKED else ""
    if n_bad:
        print(f"요약: 종료 1, 들어온 {in_rows}행, 나간 {parts_str} = {out_rows + out_empty}행, 원인 미상 {n_bad}건(ID 단위)" + picked)
    else:
        print(f"요약: 종료 0, 들어온 {in_rows}행 = {parts_str}" + picked)
    for n in NOTES:
        print(n)

    print(f"들어온 행 {in_rows}개(고유 ID {len(cin)}개" + (f", ID가 빈 행 {in_empty}개" if in_empty else "") + ")")
    print("나간 행: " + " + ".join(f"{n} {len(ids)}" for n, ids, _ in parts) + f" = {out_rows}개" +
          (f"(ID가 빈 행 {out_empty}개 따로)" if out_empty else ""))
    dup_in = {x: n for x, n in cin.items() if n > 1}
    if dup_in:
        print(f"  입력에 같은 ID가 여러 행인 ID {len(dup_in)}개(행 {sum(dup_in.values())}개): 결과 쪽에도 행 단위로 맞아야 한다. 예: " +
              ex(f"{x}×{n}" for x, n in sorted(dup_in.items())))

    if not n_bad:
        print("일치: 모든 ID가 들어온 행 수만큼 결과 쪽에 있습니다." +
              (f" (ID가 빈 행 {in_empty}개는 개수로만 맞췄습니다)" if in_empty else ""))
        return 0
    print(f"불일치: 원인 미상 {n_bad}건. 원인을 확인하기 전에는 메우지 않는다.")
    if lost:
        print(f"- 결과 쪽 어디에도 없는 ID {len(lost)}개: " + ex(lost))
    if short:
        print(f"- 결과 쪽 행이 모자란 ID {len(short)}개(중복을 지웠다면 지운 행을 '뺀' 쪽에 적는다): " + ex(short))
    if extra:
        print(f"- 입력에 없는 ID {len(extra)}개: " + ex(extra))
    if more:
        print(f"- 결과 쪽 행이 더 많은 ID {len(more)}개(같은 행이 두 번 쓰였거나 두 곳에 들어감): " + ex(more))
    if empty_bad:
        print(f"- ID가 빈 행: 입력 {in_empty}개, 결과 쪽 {out_empty}개")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(3)
    except Exception as e:  # 예상 못 한 오류도 '불일치(1)'와 헷갈리지 않게 3으로 끝낸다
        print(f"요약: 종료 3, 실행 오류: {type(e).__name__}: {e}")
        print(f"실행 오류: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(3)
