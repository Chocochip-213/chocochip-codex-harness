#!/usr/bin/env bash
# 하네스 자체 점검: 도구가 이 환경에서 도는지 본다.
# 사용: bash .harness/tools/selftest.sh   (작업 폴더는 건드리지 않고 임시 폴더에서 돈다)
set -u

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$BASE/tools"
S="$TOOLS/samples"
T="$(mktemp -d)" || { echo "임시 폴더를 만들 수 없어 자체 점검을 못 함(도구 고장이 아님)"; exit 3; }
trap 'rm -rf "$T"' EXIT

pass=0
fail=0
check() {
  local name="$1"
  shift
  if "$@" >"$T/out.txt" 2>&1; then
    echo "PASS $name"
    pass=$((pass + 1))
  else
    echo "FAIL $name"
    sed -n 1,15p "$T/out.txt" | sed 's/^/     /'
    fail=$((fail + 1))
  fi
}
exit_is() {
  local want="$1"
  shift
  "$@"
  [ $? -eq "$want" ]
}
check "env_check 실행" python3 "$TOOLS/env_check.py"
check "profile_data 실행" python3 "$TOOLS/profile_data.py" "$S"
check "profile_data가 자리표시·없는 날짜를 찾음" bash -c "python3 '$TOOLS/profile_data.py' '$S/values.csv' | grep -q '자리표시로 보이는 값' && python3 '$TOOLS/profile_data.py' '$S/values.csv' | grep -q '없는 날짜'"
check "reconcile 일치 → 종료 0" exit_is 0 python3 "$TOOLS/reconcile.py" --input "$S/values.csv:id" --part 쓴="$S/out_used.csv" --part 뺀="$S/out_excluded.csv"
check "reconcile 첫 줄이 요약" bash -c "python3 '$TOOLS/reconcile.py' --input '$S/values.csv:id' --part 쓴='$S/out_used.csv' --part 뺀='$S/out_excluded.csv' | head -1 | grep -q '^요약: 종료 0'"
check "reconcile 불일치 → 종료 1" exit_is 1 python3 "$TOOLS/reconcile.py" --input "$S/values.csv:id" --part 쓴="$S/out_used.csv"
check "reconcile 검사 0건 → 종료 2" exit_is 2 python3 "$TOOLS/reconcile.py" --input "$S/empty.csv:id" --part 쓴="$S/out_used.csv"
check "reconcile 결과의 행 목록이 비면 검사 0건 → 종료 2" bash -c "printf '{\"rows\":[]}' > '$T/rows0.json'; python3 '$TOOLS/reconcile.py' --input '$S/values.csv:id' --group '$T/rows0.json:id:s' > /dev/null; [ \$? -eq 2 ] && python3 '$TOOLS/reconcile.py' --input '$S/values.csv:id' --part 따로='$T/rows0.json:id' > /dev/null; [ \$? -eq 2 ]"
check "reconcile 열 없는 행([{}])은 실행 오류 → 종료 3" bash -c "printf '[{}]' > '$T/rows1.json'; python3 '$TOOLS/reconcile.py' --input '$S/values.csv:id' --part 쓴='$T/rows1.json:id' > /dev/null; [ \$? -eq 3 ]"
check "reconcile 결과 JSON에 객체 목록이 여럿이면 실행 오류 → 종료 3" bash -c "printf '{\"rows\":[{\"id\":\"x\"}],\"results\":[]}' > '$T/rows2.json'; python3 '$TOOLS/reconcile.py' --input '$S/values.csv:id' --part 쓴='$T/rows2.json:id' > /dev/null; [ \$? -eq 3 ]"
check "join_check 실행" python3 "$TOOLS/join_check.py" --left "$S/orders.csv:customer_id" --right "$S/customers.csv:customer_id"
check "join_check가 키 중복·표기 흔들림을 찾음" bash -c "python3 '$TOOLS/join_check.py' --left '$S/orders.csv:customer_id' --right '$S/customers.csv:customer_id' | grep -q '오른쪽 키 중복' && python3 '$TOOLS/join_check.py' --left '$S/orders.csv:customer_id' --right '$S/customers.csv:customer_id' | grep -q '표기 흔들림'"

mkdir -p "$T/todo" "$T/clean"
check "precheck가 할 일 표시를 찾음 → 종료 1" bash -c "cd '$T/todo' && printf 'x = 1  # TODO 고치기\n' > a.py; python3 '$TOOLS/precheck.py' > '$T/pc.txt'; [ \$? -eq 1 ] && grep -q 'TODO' '$T/pc.txt'"
check "precheck 찾은 것 없음 → 종료 0" bash -c "cd '$T/clean' && printf 'print(1)\n' > a.py && python3 '$TOOLS/precheck.py'"
mkdir -p "$T/stale/verify" "$T/redo/verify" "$T/vnote/verify" "$T/empty/verify"
check "precheck가 /tmp 인용·남은 검증 차이를 찾고 키는 가림 → 종료 1" bash -c "cd '$T/stale' && printf '검증: python3 /tmp/x.py --token sk-ABCDEFGHIJKLMNOPQRSTUVWX\n' > HANDOFF.md && printf 'id,diff\nA,1\n' > verify/diff_1.csv && printf '보고\n' > verify/report_1.md; python3 '$TOOLS/precheck.py' > '$T/st.txt'; [ \$? -eq 1 ] && grep -q '\[제출 문서의 /tmp 인용\] 1건' '$T/st.txt' && grep -q '\[남은 검증 차이\] 1건' '$T/st.txt' && ! grep -q 'ABCDEFGHIJKLMNOPQRSTUVWX' '$T/st.txt'"
check "precheck: 보고서 번호가 더 커도 차이 줄이 남은 diff는 경고" bash -c "cd '$T/redo' && printf 'id,diff\nA,1\n' > verify/diff_1.csv && printf '보고\n' > verify/report_1.md && printf '모두 같음\n' > verify/report_2.md; python3 '$TOOLS/precheck.py' | grep -q '남은 검증 차이 1'"
check "precheck: 머리 줄만 있는 차이 파일은 경고 없음" bash -c "cd '$T/empty' && printf 'id,diff\n' > verify/diff_1.csv; python3 '$TOOLS/precheck.py' | grep -q '남은 검증 차이 0'"
check "precheck: verify/ 안의 /tmp는 인용 경고 없음" bash -c "cd '$T/vnote' && printf '임시 결과: /tmp/x.json\n' > verify/note.md; python3 '$TOOLS/precheck.py' | grep -q '제출 문서의 /tmp 인용 0'"

echo "통과 $pass, 실패 $fail"
[ "$fail" -eq 0 ]
