#!/usr/bin/env bash
# setup.sh 시나리오 시험(하네스를 고친 뒤 돌린다). 임시 폴더에서만 돈다.
# 사용: bash dev/test_setup.sh
set -u
unset CODEX_THREAD_ID CODEX_TOOL_CALL_ID  # Codex 안에서 돌려도 사람 커밋으로 시험한다
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="$(mktemp -d)"
trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT
pass=0
fail=0
ok() { if eval "$2"; then echo "PASS $1"; pass=$((pass + 1)); else echo "FAIL $1"; fail=$((fail + 1)); fi; }
commit() { git -c user.name=t -c user.email=t@t commit -q "$@"; }
mk() { mkdir -p "$1"; cd "$1" || exit 1; git init -q -b main; echo "# 과제" > README.md; git add README.md; commit -m init; }
run() { bash "$SRC/setup.sh" >/dev/null 2>"$T/err"; }

mk "$T/a"; run; r=$?
ok "새 설치 종료 0" "[ $r -eq 0 ]"
ok "AGENTS.md 맨 앞 표시" "head -1 AGENTS.md | grep -qxF '<!-- chocochip-codex-harness -->'"
ok "규칙 파일 설치" "[ -f .codex/rules/chocochip-codex-harness.rules ]"
ok "추론 강도 설정(평소 medium, /plan high)" "grep -qx 'plan_mode_reasoning_effort = \"high\"' .codex/config.toml && git ls-files --error-unmatch .codex/config.toml >/dev/null"
ok "exclude에 .ai_env·EXPLAIN.md" "grep -qx .ai_env .git/info/exclude && grep -qx EXPLAIN.md .git/info/exclude"
ok "하네스 커밋 1개, 작업 트리 깨끗" "[ \$(git log --oneline | wc -l) -eq 2 ] && [ -z \"\$(git status --porcelain)\" ]"
ok "하네스 커밋도 형식에 맞음" "git log -1 --format=%s | grep -q '^chore(harness): 작업 도구 추가'"
ok "커밋 형식 훅 설치" "[ -x .git/hooks/commit-msg ]"
ok "Codex 커밋: 형식이 틀리면 막힘" "! CODEX_THREAD_ID=t commit --allow-empty -m update 2>/dev/null"
ok "Codex 커밋: 한국어가 없으면 막힘" "! CODEX_THREAD_ID=t commit --allow-empty -m 'feat(rules): add rule' 2>/dev/null"
ok "Codex 커밋: 형식이 맞으면 됨" "CODEX_THREAD_ID=t commit --allow-empty -m 'feat(rules): 판정 규칙 추가'"
ok "사람·플랫폼 커밋은 형식과 관계없이 됨" "commit --allow-empty -m submission"
ok "금지 규칙만 있고 허용 규칙 없음" "grep -q 'decision=\"forbidden\"' .codex/rules/chocochip-codex-harness.rules && ! grep -q 'decision=\"allow\"' .codex/rules/chocochip-codex-harness.rules"
sed -i 's/^- 과제 README와.*/- 옛 규칙 줄/' AGENTS.md; commit -am "docs: 옛 규칙"
run
ok "다시 설치하면 규칙 갱신" "! grep -q '옛 규칙 줄' AGENTS.md && [ \$(grep -cxF '<!-- chocochip-codex-harness -->' AGENTS.md) -eq 1 ]"
ok "다시 설치해도 exclude 줄 중복 없음" "[ \$(grep -cx .ai_env .git/info/exclude) -eq 1 ]"

mk "$T/b"; printf '# 과제 규칙\n- 테스트는 pytest\n' > AGENTS.md; git add AGENTS.md; commit -m agents
run; run
ok "과제 AGENTS.md 보존, 두 번 설치해도 한 번만" "head -1 AGENTS.md | grep -q '과제 규칙' && grep -q pytest AGENTS.md && [ \$(grep -cxF '<!-- chocochip-codex-harness -->' AGENTS.md) -eq 1 ]"

mk "$T/g"; mkdir .codex; echo 'model = "x"' > .codex/config.toml; git add .codex; commit -m cfg; run
ok "과제의 .codex/config.toml은 그대로" "[ \"\$(cat .codex/config.toml)\" = 'model = \"x\"' ] && [ -z \"\$(git status --porcelain)\" ]"

mk "$T/h"; printf '#!/bin/sh\nexit 0\n' > .git/hooks/commit-msg; chmod +x .git/hooks/commit-msg; run
ok "과제의 commit-msg 훅은 그대로" "! grep -q chocochip .git/hooks/commit-msg"

mk "$T/c"; mkdir .harness; run; r=$?
ok "빈 .harness는 이어서 설치" "[ $r -eq 0 ] && [ -f .harness/SOURCE.txt ]"

mk "$T/d"; mkdir .harness; echo x > .harness/mine.txt; run; r=$?
ok "과제 .harness가 있으면 멈추고 아무것도 안 바꿈" "[ $r -eq 1 ] && [ ! -e .agents ] && [ ! -e AGENTS.md ]"

mk "$T/e"; mkdir -p .agents/skills/verify; echo x > .agents/skills/verify/SKILL.md; run; r=$?
ok "같은 이름 스킬이 있으면 멈춤" "[ $r -eq 1 ] && [ ! -e .harness ]"

mk "$T/f"; chmod a-w .; run; r=$?; chmod u+w .
ok "쓰기가 막히면 아무것도 안 만들고 안내" "[ $r -eq 1 ] && [ ! -e .harness ] && grep -q '쓰기가 막혔습니다' '$T/err'"

echo "통과 $pass, 실패 $fail"
[ "$fail" -eq 0 ]
