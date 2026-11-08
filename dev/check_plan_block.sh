#!/usr/bin/env bash
# 계획 블록(①~⑧) 세 사본이 같은지 본다: 치트시트·README의 text 블록과 relay 스킬이 보이는 따옴표 안 문장.
# 공백·줄바꿈은 빼고 비교한다. 블록을 고친 뒤 커밋 전에 돌린다.
# 사용: bash dev/check_plan_block.sh [하네스 폴더]
set -u
SRC="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
HEAD="계획 문서에서는 '개발 시작 메모' 절만 읽고"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT

block() {
  awk -v h="$HEAD" '
    /^```text$/ { on = 1; buf = ""; first = ""; next }
    on && /^```$/ { if (index(first, h) == 1) { printf "%s", buf; exit } on = 0; next }
    on { if (first == "") first = $0; buf = buf $0 "\n" }
  ' "$1" | tr -d ' \t\r\n'
}

block "$SRC/playbook/cheatsheet.md" > "$T/cheatsheet"
block "$SRC/README.md" > "$T/readme"
grep -o "\"$HEAD[^\"]*\"" "$SRC/.agents/skills/relay/SKILL.md" | head -1 | tr -d '" \t\r\n' > "$T/relay"

for f in cheatsheet readme relay; do
  [ -s "$T/$f" ] || { echo "블록을 못 찾음: $f"; exit 1; }
done

rc=0
for f in readme relay; do
  if ! cmp -s "$T/cheatsheet" "$T/$f"; then
    off="$(cmp "$T/cheatsheet" "$T/$f" 2>&1 | grep -o -E '(byte|char) [0-9]+' | grep -o -E '[0-9]+' | head -1)"
    from=$(( ${off:-1} > 40 ? ${off:-1} - 40 : 1 ))
    echo "다름: cheatsheet ↔ $f (${off:-?}바이트 근처, 공백 뺀 글)"
    echo "  cheatsheet: $(tail -c +"$from" "$T/cheatsheet" | head -c 120)"
    echo "  $f: $(tail -c +"$from" "$T/$f" | head -c 120)"
    rc=1
  fi
done
[ "$rc" -eq 0 ] && echo "계획 블록 세 사본 일치($(wc -c < "$T/cheatsheet")바이트, 공백 뺀 글)"
exit "$rc"
