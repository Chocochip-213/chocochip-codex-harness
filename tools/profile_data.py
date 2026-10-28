#!/usr/bin/env python3
"""데이터 점검: 파일·표마다 행 수와 열별 결측, 자리표시 값(N/A·미정 등), 값 종류, 숫자 범위·음수·0·IQR 밖 값,
날짜 모양 섞임과 없는 날짜, 표기만 다른 값, 앞뒤 공백, ID 열의 중복, 완전히 같은 행, 이메일·전화번호 모양을 숫자로 보여 준다.

사용:
  python3 profile_data.py data                        # 폴더 안의 데이터 파일 전부(하위 폴더 포함)
  python3 profile_data.py data/a.csv b.json
  python3 profile_data.py data --key order_id+line_no  # 여러 열을 합친 키의 중복도 본다(여러 번 가능)
  python3 profile_data.py data --top 5                # 많은 값을 몇 개까지 보여 줄지
  python3 profile_data.py data --all                  # 예시를 자르지 않고 전부 보여 줌

읽는 형식: .csv .tsv .json(객체 목록) .jsonl .db .sqlite .sqlite3
행 번호: CSV는 헤더를 1행으로 센 번호(엑셀과 같음), JSON·SQLite는 1부터 센 순번.
개수는 항상 전체를 센다. 예시 값만 일부 보여 주고, 잘린 곳에는 '외 N'을 붙인다(--all이면 자르지 않음).
표준 라이브러리만 쓴다. 파일 내용 전체를 출력하지 않고, 이메일·전화번호는 가려서 출력한다.
"""
import argparse
import csv
import datetime as dt
import io
import json
import re
import sqlite3
import statistics
import sys
import unicodedata
from pathlib import Path

import signal
if hasattr(signal, "SIGPIPE"):  # 출력을 head 등으로 자를 때 오류 없이 끝낸다
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

ENCODINGS = ("utf-8-sig", "cp949")
DATA_EXT = {".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".db", ".sqlite", ".sqlite3"}
SKIP_DIRS = {".git", ".harness", ".agents", "node_modules", ".venv", "venv", "__pycache__"}
UNIQUE_CAP = 200000         # 일반 열은 값 종류를 여기까지만 센다(넘으면 건너뛴 점검을 출력에 적는다)
KEY_CAP = 2000000           # ID처럼 보이는 열은 중복을 찾으려고 끝까지 센다
SQL_ROW_CAP = 500000
csv.field_size_limit(2**31 - 1)
SHOW_ALL = False            # --all이면 예시를 자르지 않는다


def keep(lst, n):
    """예시를 n개까지만 모은다(--all이면 전부)."""
    return SHOW_ALL or len(lst) < n


def cut(seq, n):
    """보여 줄 예시를 n개로 자르고, 잘렸으면 '외 N' 꼬리를 돌려준다."""
    seq = list(seq)
    if SHOW_ALL or len(seq) <= n:
        return seq, ""
    return seq[:n], f" 외 {len(seq) - n}개"

DATE_LIKE = re.compile(
    r"^(\d{4}\s*[-/.년]\s*\d{1,2}\s*[-/.월]\s*\d{1,2}"   # 2024-10-03, 2024/10/3, 2024.10.03, 2024년 10월 3일
    r"|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"                 # 10/03/2024
    r"|\d{1,2}:\d{2})"                                   # 14:05
)
YMD = re.compile(r"^(\d{4})\s*[-/.년]\s*(\d{1,2})\s*[-/.월]\s*(\d{1,2})\s*일?"
                 r"(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?")
HM = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")
COMPACT_DATE = re.compile(r"^(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])([ T]?\d{4}(\d{2})?)?$")
DATE_NAME = re.compile(r"(date|time|_at$|^ts$|_ts$|dt$|일자|일시|시각|날짜|시간|기간|월일)", re.I)
NUM = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")
ID_NAME = re.compile(r"(^id$|_id$|id$|^no$|_no$|번호$|아이디|^key$|_key$)", re.I)
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\d)(01[016789]|0\d{1,2})[-. ]?\d{3,4}[-. ]?\d{4}(?!\d)")
RRN = re.compile(r"(?<!\d)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])-?[1-8]\d{6}(?!\d)")  # 주민·외국인등록번호 모양
# 값이 비어 있지는 않지만 '값 없음'을 뜻할 수 있는 표기(대소문자 무시)
PLACEHOLDERS = {"n/a", "na", "n.a.", "#n/a", "null", "none", "nil", "nan", "unknown", "unk", "-", "--", "—",
                "?", "tbd", "tba", "미정", "없음", "해당없음", "해당 없음", "미상", "모름", "확인중", "확인 중"}
# 숫자 열에서 '값 없음' 대신 넣는 경우가 많은 숫자(실제 값일 수도 있어 '의심'으로만 보인다)
SENTINELS = {-1.0, -9.0, -99.0, -999.0, -9999.0, 9999.0, 99999.0, 999999.0}


def decode(raw):
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace"), "utf-8(깨진 글자 있음)"


def shape(v):
    return re.sub(r"\d", "9", v)


def short(v, n=40):
    v = str(v).replace("\r\n", "⏎").replace("\n", "⏎").replace("\r", "⏎")
    v = PHONE.sub("<전화번호>", RRN.sub("<등록번호>", EMAIL.sub("<이메일>", v)))
    return v if len(v) <= n else v[: n - 1] + "…"


def bad_date(s):
    """날짜·시각 모양인데 실제로는 없는 날짜·시각이면 True"""
    m = YMD.match(s)
    try:
        if m:
            y, mo, d, h, mi, se = (int(x) if x else 0 for x in m.groups())
            dt.datetime(y, mo, d, h, mi, se)
            return False
        m = HM.match(s)
        if m:
            h, mi, se = (int(x) if x else 0 for x in m.groups())
            return not (h <= 24 and mi <= 59 and se <= 59)
    except ValueError:
        return True
    return False


class Col:
    def __init__(self, name, date_hint, key_like, pk_like=False):
        self.name = name
        self.date_hint = date_hint
        self.key_like = key_like
        self.pk_like = pk_like      # 첫 열이거나 이름이 id인 열: 중복이면 행 수와 상관없이 보인다
        self.rrn = 0
        self.missing = 0
        self.filled = 0
        self.counts = {}
        self.capped = False
        self.num = 0
        self.num_min = None
        self.num_max = None
        self.nonnum = []
        self.lead0 = 0
        self.shapes = {}
        self.bad_dates = []
        self.bad_n = 0
        self.space = []
        self.space_n = 0
        self.newline = 0
        self.email = 0
        self.phone = 0
        self.placeholders = {}
        self.nums = []

    def add(self, v, rowno):
        if v is None:
            self.missing += 1
            return
        if not isinstance(v, str):
            v = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
        s = v.strip()
        if s == "":
            self.missing += 1
            return
        self.filled += 1
        if s.casefold() in PLACEHOLDERS:
            self.placeholders[s] = self.placeholders.get(s, 0) + 1
        if "\n" in s or "\r" in s:
            self.newline += 1
        if v != s:
            self.space_n += 1
            if keep(self.space, 3):
                self.space.append((rowno, v))
        if "@" in s and EMAIL.search(s):
            self.email += 1
        if PHONE.search(s) and not DATE_LIKE.match(s):
            self.phone += 1
        if RRN.search(s):
            self.rrn += 1
        if not self.capped:
            self.counts[s] = self.counts.get(s, 0) + 1
            if len(self.counts) > (KEY_CAP if self.key_like else UNIQUE_CAP):
                self.capped = True
        t = s.replace(",", "")
        if NUM.match(t):
            x = float(t)
            self.nums.append(x)
            self.num += 1
            self.num_min = x if self.num_min is None else min(self.num_min, x)
            self.num_max = x if self.num_max is None else max(self.num_max, x)
            if len(t) > 1 and t[0] == "0" and t[1].isdigit():
                self.lead0 += 1
        elif keep(self.nonnum, 5):
            self.nonnum.append((rowno, s))
        if DATE_LIKE.match(s) or (self.date_hint and COMPACT_DATE.match(s)):
            sh = shape(s)
            e = self.shapes.get(sh)
            if e is None:
                self.shapes[sh] = [1, s, s, rowno]
            else:
                e[0] += 1
                e[1] = min(e[1], s)
                e[2] = max(e[2], s)
            if bad_date(s):
                self.bad_n += 1
                if keep(self.bad_dates, 3):
                    self.bad_dates.append((rowno, s))

    def numeric_report(self):
        """숫자 열: 음수·0 개수, 센티넬 의심 값, IQR(사분위 범위) 밖 값."""
        out = []
        xs = self.nums
        neg = sum(1 for x in xs if x < 0)
        zero = sum(1 for x in xs if x == 0)
        sent = {}
        for x in xs:
            if x in SENTINELS:
                sent[x] = sent.get(x, 0) + 1
        bits = []
        if neg:
            bits.append(f"음수 {neg}개")
        if zero:
            bits.append(f"0 {zero}개")
        if sent:
            bits.append("센티넬 의심 " + ", ".join(f"{fmt(k)}×{n}" for k, n in sorted(sent.items())))
        if len(xs) >= 8:
            q1, _, q3 = statistics.quantiles(xs, n=4)
            iqr = q3 - q1
            if iqr > 0:
                lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                outside = [x for x in xs if x < lo or x > hi]
                if outside:
                    bits.append(f"IQR 밖 {len(outside)}개(기준 {fmt(lo)}~{fmt(hi)}, 실제 {fmt(min(outside))}~{fmt(max(outside))})")
        if bits:
            out.append("    숫자 살펴볼 것: " + " · ".join(bits))
        return out

    def report(self, top, rowword):
        out = []
        uniq = f"{len(self.counts)}+" if self.capped else str(len(self.counts))
        parts = [f"결측 {self.missing}", f"값 종류 {uniq}"]
        if self.filled and self.num == self.filled:
            parts.append(f"숫자 {fmt(self.num_min)}~{fmt(self.num_max)}")
            if self.lead0:
                parts.append(f"앞자리 0인 값 {self.lead0}개(숫자로 바꾸면 0이 사라짐)")
        elif self.num and self.num >= self.filled * 0.5:
            shown, _ = cut(self.nonnum, 3)
            ex = ", ".join(f"{rowword}{r} '{short(v)}'" for r, v in shown)
            parts.append(f"숫자 {self.num}개에 숫자 아닌 값 {self.filled - self.num}개 섞임(예: {ex})")
        out.append(f"- {self.name}: " + " · ".join(parts))
        if self.placeholders:
            ph = sorted(self.placeholders.items(), key=lambda kv: -kv[1])
            out.append(f"    자리표시로 보이는 값 {sum(n for _, n in ph)}개: " +
                       ", ".join(f"'{k}'×{n}" for k, n in ph))
        if self.num and self.num >= self.filled * 0.5:
            out.extend(self.numeric_report())
        if self.shapes:
            dated = sum(e[0] for e in self.shapes.values())
            rows = sorted(self.shapes.items(), key=lambda kv: -kv[1][0])
            shown, tail = cut(rows, 4)
            desc = "; ".join(
                f"{sh} ×{e[0]}" + (f" ({e[1]} ~ {e[2]})" if e[0] > 1 else f" ({rowword}{e[3]} '{e[1]}')")
                for sh, e in shown)
            label = "날짜·시각 모양 섞임" if len(rows) > 1 else "날짜·시각 모양"
            out.append(f"    {label}: {desc}{tail}")
            if 0 < self.filled - dated and dated >= self.filled * 0.5:
                out.append(f"    날짜·시각 모양이 아닌 값 {self.filled - dated}개")
            if self.bad_n:
                out.append(f"    없는 날짜·시각 {self.bad_n}개: " +
                           ", ".join(f"{rowword}{r} '{v}'" for r, v in self.bad_dates) +
                           (f" 외 {self.bad_n - len(self.bad_dates)}개" if self.bad_n > len(self.bad_dates) else ""))
        if self.counts and not self.capped:
            ranked = sorted(self.counts.items(), key=lambda kv: (-kv[1], kv[0]))
            near_unique = len(self.counts) >= 0.9 * self.filled
            if len(ranked) <= 15:
                out.append("    값: " + ", ".join(f"{short(k, 30)}({n})" for k, n in ranked))
            elif ranked[0][1] > 1 and not near_unique:
                shown, tail = cut(ranked, top)
                out.append("    많은 값: " + ", ".join(f"{short(k, 30)}({n})" for k, n in shown) + tail)
            groups = {}
            for k in self.counts:
                key = re.sub(r"[\s_\-]", "", unicodedata.normalize("NFKC", k)).upper()
                groups.setdefault(key, []).append(k)
            variants = [sorted(g) for g in groups.values() if len(g) > 1]
            if variants:
                shown, tail = cut(variants, 5)
                out.append(f"    표기만 다른 값 {len(variants)}묶음(같은 것일 수 있음): " +
                           "; ".join(" / ".join(short(x, 25) for x in g) for g in shown) + tail)
            dups = [(k, n) for k, n in ranked if n > 1]
            if dups and (self.pk_like or (self.key_like and self.filled >= 20 and near_unique)):
                shown, tail = cut(dups, 5)
                out.append(f"    ID처럼 보이는데 중복 {len(dups)}개 값: " +
                           ", ".join(f"{short(k, 25)}×{n}" for k, n in shown) + tail)
        elif self.capped:
            out.append(f"    값 종류가 {UNIQUE_CAP:,}개를 넘어 값 목록·표기 변형·중복 점검을 건너뛰었다"
                       "(ID처럼 보이는 열은 끝까지 센다)")
        if self.space_n:
            out.append(f"    앞뒤 공백 {self.space_n}개: " +
                       ", ".join(f"{rowword}{r} '{short(v)}'" for r, v in self.space) +
                       (f" 외 {self.space_n - len(self.space)}개" if self.space_n > len(self.space) else ""))
        if self.newline:
            out.append(f"    줄바꿈이 들어 있는 값 {self.newline}개")
        if self.email or self.phone or self.rrn:
            out.append(f"    개인정보 모양: 이메일 {self.email}개, 전화번호 {self.phone}개, 주민·외국인등록번호 {self.rrn}개(출력에서는 가림)")
        return out


def fmt(x):
    if x is None:
        return "-"
    return str(int(x)) if float(x).is_integer() and abs(x) < 1e15 else f"{x:g}"


def profile(title, header, rows, top, rowword, keys, extra=None):
    """rows: (행 번호, 값 목록) 반복자. keys: 합친 키로 중복을 볼 열 이름 목록들"""
    print(f"\n== {title}")
    for line in extra or []:
        print(line)
    names = [str(h) if str(h).strip() else f"(빈 이름 {i + 1}번째 열)" for i, h in enumerate(header)]
    seen_names = {}
    for n in names:
        seen_names[n] = seen_names.get(n, 0) + 1
    if any(c > 1 for c in seen_names.values()):
        print("  같은 이름의 열: " + ", ".join(f"{n}×{c}" for n, c in seen_names.items() if c > 1))
    spaced = [n for n in names if n != n.strip()]
    if spaced:
        print("  열 이름에 앞뒤 공백: " + ", ".join(repr(n) for n in spaced))
    cols = [Col(n, bool(DATE_NAME.search(n)), i == 0 or bool(ID_NAME.search(n.strip())),
                pk_like=(i == 0 or n.strip().lower() == "id"))
            for i, n in enumerate(names)]
    stripped = [n.strip() for n in names]
    key_idx = []
    for k in keys:
        want = [c.strip() for c in k.split("+")]
        if all(c in stripped for c in want):
            key_idx.append((k, [stripped.index(c) for c in want], {}))
        else:
            print(f"  키 {k}: 이 파일에 없는 열 {[c for c in want if c not in stripped]} — 이 파일은 건너뜀")
    nrows = blank = 0
    width_bad, width_n = [], 0
    first_seen, dup_ex, dup_n = {}, [], 0
    for rowno, vals in rows:
        if all(v is None or (isinstance(v, str) and not v.strip()) for v in vals):
            blank += 1
            continue
        nrows += 1
        if len(vals) != len(cols):
            width_n += 1
            if keep(width_bad, 3):
                width_bad.append((rowno, len(vals)))
        key = "\x1f".join("" if v is None else str(v).strip() for v in vals)
        if key in first_seen:
            dup_n += 1
            if keep(dup_ex, 3):
                dup_ex.append((first_seen[key], rowno))
        else:
            first_seen[key] = rowno
        for j, c in enumerate(cols):
            c.add(vals[j] if j < len(vals) else None, rowno)
        for _, idx, seen in key_idx:
            kv = tuple("" if j >= len(vals) or vals[j] is None else str(vals[j]).strip() for j in idx)
            seen.setdefault(kv, []).append(rowno)
    print(f"행 {nrows}개, 열 {len(cols)}개" + (f", 빈 행 {blank}개" if blank else ""))
    if width_n:
        print(f"  열 개수가 헤더({len(cols)}칸)와 다른 행 {width_n}개: " +
              ", ".join(f"{rowword}{r}({n}칸)" for r, n in width_bad))
    if dup_n:
        print(f"  완전히 같은 행 {dup_n}개: " + ", ".join(f"{rowword}{a} = {rowword}{b}" for a, b in dup_ex))
    for k, _, seen in key_idx:
        dups = [(kv, rs) for kv, rs in seen.items() if len(rs) > 1]
        msg = f"  키 {k}: 고유 {len(seen)}개 / 행 {nrows}개"
        if dups:
            shown, tail = cut(dups, 3)
            msg += f", 두 번 이상 나온 키 {len(dups)}개(예: " + "; ".join(
                f"{'+'.join(kv)} → {', '.join(rowword + str(r) for r in cut(rs, 3)[0])}" for kv, rs in shown) + tail + ")"
        print(msg)
    for c in cols:
        for line in c.report(top, rowword):
            print(line)


def csv_file(path, top, keys):
    text, enc = decode(path.read_bytes())
    if not text.strip():
        print(f"\n== {path}: 빈 파일")
        return
    if path.suffix.lower() == ".tsv":
        delim = "\t"
    else:
        try:
            delim = csv.Sniffer().sniff(text[:8192], delimiters=",\t;|").delimiter
        except csv.Error:
            delim = ","
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    header = next(reader)

    def rows():  # 번호는 헤더를 1행으로 센 엑셀 행 번호(값 안에 줄바꿈이 있어도 행 단위로 센다)
        for rowno, rec in enumerate(reader, start=2):
            yield rowno, rec

    profile(f"{path}  ({enc}, 구분자 {delim!r})", header, rows(), top, "행 ", keys)


def json_records(path):
    text, enc = decode(path.read_bytes())
    if path.suffix.lower() in (".jsonl", ".ndjson"):
        recs, bad = [], 0
        for ln in text.splitlines():
            if ln.strip():
                try:
                    recs.append(json.loads(ln))
                except json.JSONDecodeError:
                    bad += 1
        return recs, enc, ([f"  JSON으로 읽지 못한 줄 {bad}개"] if bad else [])
    data = json.loads(text)
    note = []
    if isinstance(data, dict):
        lists = [(k, v) for k, v in data.items() if isinstance(v, list) and v and isinstance(v[0], dict)]
        if not lists:
            shown, tail = cut(list(data), 10)
            return None, enc, ["  객체 목록이 없어 표로 볼 수 없습니다. 최상위 키: " + ", ".join(shown) + tail]
        for k, v in lists[1:]:
            note.append(f"  다른 목록도 있음: '{k}' {len(v)}개(따로 보려면 그 목록만 꺼내서 확인)")
        k, data = lists[0]
        note.insert(0, f"  최상위 키 '{k}'의 목록을 봤습니다")
    if not isinstance(data, list):
        return None, enc, ["  목록이 아닙니다"]
    return data, enc, note


def json_file(path, top, keys):
    try:
        recs, enc, note = json_records(path)
    except json.JSONDecodeError as e:
        print(f"\n== {path}: JSON으로 읽지 못함 ({e})")
        return
    if recs is None:
        print(f"\n== {path}")
        for n in note:
            print(n)
        return
    dicts = [r for r in recs if isinstance(r, dict)]
    if len(dicts) != len(recs):
        note.append(f"  객체가 아닌 항목 {len(recs) - len(dicts)}개는 건너뜀")
    header, seen = [], set()
    for r in dicts:
        for k in r:
            if k not in seen:
                seen.add(k)
                header.append(k)
    gaps = []
    for k in header:
        n = sum(1 for r in dicts if k not in r)
        if n:
            gaps.append(f"{k}({n})")
    if gaps:
        shown, tail = cut(gaps, 10)
        note.append("  키가 아예 없는 항목 수(결측에 포함): " + ", ".join(shown) + tail)
    rows = ((i, [r.get(k) for k in header]) for i, r in enumerate(dicts, start=1))
    profile(f"{path}  ({enc})", header, rows, top, "#", keys, note)


def sqlite_file(path, top, keys):
    con = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        tables = [r[0] for r in con.execute(
            "select name from sqlite_master where type in ('table','view') and name not like 'sqlite_%' order by name")]
        print(f"\n== {path}  (SQLite 표 {len(tables)}개: {', '.join(tables)})")
        for t in tables:
            q = '"' + t.replace('"', '""') + '"'
            total = con.execute(f"select count(*) from {q}").fetchone()[0]
            cur = con.execute(f"select * from {q} limit {SQL_ROW_CAP}")
            header = [d[0] for d in cur.description]
            extra = [f"  앞 {SQL_ROW_CAP}행만 봄(전체 {total}행)"] if total > SQL_ROW_CAP else []
            rows = ((i, list(r)) for i, r in enumerate(cur, start=1))
            profile(f"{path} :: {t}", header, rows, top, "#", keys, extra)
    finally:
        con.close()


def collect(paths):
    files = []
    for p in map(Path, paths):
        if p.is_dir():
            found = [f for f in sorted(p.rglob("*"))
                     if f.is_file() and not (set(f.relative_to(p).parts[:-1]) & SKIP_DIRS)]
            files += [f for f in found if f.suffix.lower() in DATA_EXT]
            skipped = [str(f.relative_to(p)) for f in found if f.suffix.lower() not in DATA_EXT]
            if skipped:
                shown, tail = cut(skipped, 10)
                print(f"(이 도구가 읽지 않아 건너뛴 파일 {len(skipped)}개: {', '.join(shown)}{tail} — 필요하면 직접 본다)")
        elif p.is_file():
            files.append(p)
        else:
            print(f"없는 경로: {p}", file=sys.stderr)
    return files


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--key", action="append", default=[], help="중복을 볼 합친 키, 예: order_id+line_no")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--all", action="store_true", help="예시를 자르지 않고 전부 보여 준다")
    a = ap.parse_args()
    global SHOW_ALL
    SHOW_ALL = a.all
    if not a.all:
        print("(개수는 전체입니다. 예시만 일부 보여 주고, 잘린 곳에는 '외 N'을 붙입니다. 전부 보려면 --all)")
    files = collect(a.paths)
    if not files:
        print("읽을 데이터 파일이 없습니다.", file=sys.stderr)
        return 1
    for f in files:
        ext = f.suffix.lower()
        try:
            if ext in (".json", ".jsonl", ".ndjson"):
                json_file(f, a.top, a.key)
            elif ext in (".db", ".sqlite", ".sqlite3"):
                sqlite_file(f, a.top, a.key)
            else:
                csv_file(f, a.top, a.key)
        except Exception as e:  # 한 파일이 실패해도 나머지는 본다
            print(f"\n== {f}: 읽다가 오류 ({type(e).__name__}: {e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
