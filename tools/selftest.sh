#!/usr/bin/env bash
# 하네스 자체 점검: 도구가 이 환경에서 도는지 본다.
# 사용: bash .harness/tools/selftest.sh   (작업 폴더는 건드리지 않고 임시 폴더에서 돈다)
set -u

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$BASE/tools"
S="$TOOLS/samples"
T="$(mktemp -d)"
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
check "reconcile 불일치 → 종료 1" exit_is 1 python3 "$TOOLS/reconcile.py" --input "$S/values.csv:id" --part 쓴="$S/out_used.csv"
check "reconcile 검사 0건 → 종료 2" exit_is 2 python3 "$TOOLS/reconcile.py" --input "$S/empty.csv:id" --part 쓴="$S/out_used.csv"
check "join_check 실행" python3 "$TOOLS/join_check.py" --left "$S/orders.csv:customer_id" --right "$S/customers.csv:customer_id"
check "join_check가 키 중복·표기 흔들림을 찾음" bash -c "python3 '$TOOLS/join_check.py' --left '$S/orders.csv:customer_id' --right '$S/customers.csv:customer_id' | grep -q '오른쪽 키 중복' && python3 '$TOOLS/join_check.py' --left '$S/orders.csv:customer_id' --right '$S/customers.csv:customer_id' | grep -q '표기 흔들림'"

mkdir -p "$T/todo" "$T/clean"
check "precheck가 할 일 표시를 찾음 → 종료 1" bash -c "cd '$T/todo' && printf 'x = 1  # TODO 고치기\n' > a.py; python3 '$TOOLS/precheck.py' > '$T/pc.txt'; [ \$? -eq 1 ] && grep -q 'TODO' '$T/pc.txt'"
check "precheck 찾은 것 없음 → 종료 0" bash -c "cd '$T/clean' && printf 'print(1)\n' > a.py && python3 '$TOOLS/precheck.py'"

echo "통과 $pass, 실패 $fail"
[ "$fail" -eq 0 ]
