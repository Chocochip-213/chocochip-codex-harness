#!/usr/bin/env bash
# chocochip-codex-harness 설치: 과제 작업 폴더에 작업 규칙(AGENTS.md), 스킬(.agents/skills), 점검 도구(.harness)를 넣는다.
#
# 사용: 과제 작업 폴더 맨 위에서(shell 탭이든 Codex에게 시키든 같은 한 줄)
#   git clone --depth 1 https://github.com/Chocochip-213/chocochip-codex-harness /tmp/h && bash /tmp/h/setup.sh
# 작업 폴더를 따로 지정하려면: bash /tmp/h/setup.sh <작업 폴더>
# 여러 번 실행해도 된다(하네스 파일만 새로 덮어쓰고, AGENTS.md에는 한 번만 덧붙인다).
# 과제에 같은 폴더 이름의 스킬이나 하네스가 만들지 않은 .harness 폴더가 있으면 아무것도 바꾸지 않고 멈춘다.
# Codex가 설치할 때: 이 스크립트를 과제 폴더에서 한 번 실행하면 끝이다. .agents·.codex·.git에 쓰므로 승인 창이 뜰 수 있고(횟수는 환경마다 다르다), 다른 문서는 찾아볼 필요 없다.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
DST="$(cd "${1:-.}" && pwd -P)"
ERR="$(mktemp)"
trap 'rm -f "$ERR"' EXIT
first_err() { head -n 1 "$ERR" | sed -E 's/[.[:space:]]+$//'; }

HOME_P="$(cd "${HOME:-/}" 2>/dev/null && pwd -P || echo /)"
if [ "$DST" = "/" ] || [ "$DST" = "$HOME_P" ]; then
  echo "홈 폴더나 / 에는 설치하지 않습니다. 과제 작업 폴더로 cd 한 뒤 실행하세요." >&2
  exit 1
fi
if [ "$SRC" = "$DST" ]; then
  echo "하네스 폴더가 아니라 과제 작업 폴더에서 실행하세요." >&2
  exit 1
fi
case "$DST/" in
  "$SRC/"*) echo "작업 폴더가 하네스 폴더 안에 있습니다. 과제 작업 폴더에서 실행하세요." >&2; exit 1 ;;
esac
case "$SRC/" in
  "$DST/"*) echo "주의: 하네스를 작업 폴더 안($SRC)에 받았습니다. 작업 폴더 밖(/tmp/h)에 받는 것이 좋습니다." >&2 ;;
esac

# 과제 파일과 겹치는지 먼저 본다(겹치면 아무것도 바꾸지 않고 멈춘다)
H="$DST/.harness"
MANIFEST="$H/INSTALLED_SKILLS"
ours=0
if [ -e "$H/SOURCE.txt" ] || [ -e "$H/INSTALLING" ]; then ours=1; fi
if [ -d "$H" ] && [ -z "$(ls -A "$H" 2>/dev/null)" ]; then ours=1; fi
if [ -e "$H" ] && [ "$ours" -eq 0 ]; then
  echo "과제에 .harness 폴더가 이미 있어 멈춥니다(하네스가 만든 폴더가 아님). 아무것도 바꾸지 않았습니다." >&2
  exit 1
fi
skills=()
for s in "$SRC/.agents/skills"/*/; do
  name="$(basename "$s")"
  skills+=("$name")
  # 같은 이름의 폴더는 하네스가 전에 깐 것일 때만 덮어쓴다(목록에 있거나, 목록이 없던 예전·중단된 설치)
  if [ -e "$DST/.agents/skills/$name" ]; then
    if [ "$ours" -eq 0 ] || { [ -e "$MANIFEST" ] && ! grep -qxF "$name" "$MANIFEST"; }; then
      echo "과제에 같은 이름의 스킬(.agents/skills/$name)이 있어 멈춥니다. 덮어쓰면 과제 스킬이 사라집니다. 아무것도 바꾸지 않았습니다." >&2
      exit 1
    fi
  fi
done
for name in "${skills[@]}"; do
  for f in "$DST"/.agents/skills/*/SKILL.md; do
    [ -e "$f" ] || continue
    d="$(basename "$(dirname "$f")")"
    [ "$d" = "$name" ] && continue
    if grep -qE "^name:[[:space:]]*[\"']?$name[\"']?[[:space:]]*$" "$f"; then
      echo "주의: 과제 스킬 .agents/skills/$d 의 이름도 $name 입니다. \$$name 이 어느 쪽을 부를지 모르니 '.agents/skills/$name/SKILL.md를 읽고 그대로 해 줘'로 부르세요." >&2
    fi
  done
done

if ! compgen -G "$DST/[Rr][Ee][Aa][Dd][Mm][Ee]*" >/dev/null; then
  echo "주의: $DST 에 README가 없습니다. 과제 작업 폴더가 맞는지 확인하세요." >&2
fi
if [ -e "$DST/AGENTS.override.md" ]; then
  echo "주의: AGENTS.override.md가 있어 Codex가 AGENTS.md 대신 그 파일을 읽을 수 있습니다. 과제 파일이니 고치지 말고, \$kickoff로 AGENTS.md를 읽게 하세요." >&2
fi

is_root=0
if git -C "$DST" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  top="$(cd "$(git -C "$DST" rev-parse --show-toplevel)" && pwd -P)"
  [ "$top" = "$DST" ] && is_root=1
fi

# Codex 샌드박스는 .agents·.codex·.git을 읽기 전용으로 둔다. 무엇이든 만들기 전에 막혔는지 본다
if ! mkdir -p "$DST/.agents/skills" "$DST/.codex/rules" 2>"$ERR"; then
  echo "쓰기가 막혔습니다: $(first_err). Codex 샌드박스에서는 .agents·.codex가 읽기 전용입니다. 승인을 받아 같은 명령을 다시 실행하거나, shell 탭에서 bash $SRC/setup.sh 를 실행하세요. 아무것도 바꾸지 않았습니다." >&2
  exit 1
fi
mkdir -p "$H"
: > "$H/INSTALLING"  # 중간에 멈췄을 때 다시 실행하면 이어서 깔 수 있게 하는 표시(끝나면 지운다)
if [ "$is_root" -eq 1 ] && [ ! -e "$H/BASE" ]; then
  # 설치 직전의 커밋. 마감 검토($wrapup)가 과제 작업 전체를 볼 기준으로 쓴다. 처음 설치할 때만 적는다
  git -C "$DST" rev-parse --verify -q HEAD > "$H/BASE" || : > "$H/BASE"
fi
for d in tools vendor; do
  rm -rf "${H:?}/$d"
  cp -R "$SRC/$d" "$H/$d"
done
find "$H" -name __pycache__ -prune -exec rm -rf {} +
cp "$SRC/playbook/cheatsheet.md" "$H/cheatsheet.md"
cp "$SRC/playbook/LIBS.md" "$H/LIBS.md"
for name in "${skills[@]}"; do
  rm -rf "$DST/.agents/skills/${name:?}"
  cp -R "$SRC/.agents/skills/$name" "$DST/.agents/skills/$name"
done
printf '%s\n' "${skills[@]}" > "$MANIFEST"
# git push·원격 추가·gh·--no-verify 커밋을 막는 Codex 규칙(막는 규칙만, 허용 규칙 없음). 새 세션부터 읽힌다
cp "$SRC/codex/rules/chocochip-codex-harness.rules" "$DST/.codex/rules/chocochip-codex-harness.rules"
paths=(AGENTS.md .agents .harness .codex/rules/chocochip-codex-harness.rules)
# 추론 강도(평소 medium, /plan high). 과제에 .codex/config.toml이 있으면 건드리지 않는다
CFG="$DST/.codex/config.toml"
if [ ! -e "$CFG" ] || grep -qF "# chocochip-codex-harness" "$CFG"; then
  cp "$SRC/codex/config.toml" "$CFG"
  paths+=(.codex/config.toml)
  cfg_msg="추론 강도: .codex/config.toml (평소 medium, /plan high. 상태 줄에서 확인)"
else
  cfg_msg="추론 강도: 과제의 .codex/config.toml이 있어 넣지 않았습니다. /plan 전에 /model에서 high를 고르세요"
fi

# 키 파일과 사용자용 설명 노트(EXPLAIN.md)가 git add로 섞여 들어가지 않게 이 저장소에서만 제외한다(.gitignore는 건드리지 않는다)
hook_msg="커밋 형식 훅: git 저장소가 아니라 넣지 않았습니다"
if gd="$(git -C "$DST" rev-parse --absolute-git-dir 2>/dev/null)"; then
  ex="$gd/info/exclude"
  mkdir -p "$gd/info" 2>/dev/null
  for pat in "# chocochip-codex-harness" ".env" ".env.*" ".ai_env" "__pycache__/" "*.pyc" "EXPLAIN.md"; do
    grep -qxF -- "$pat" "$ex" 2>/dev/null || printf '%s\n' "$pat" >> "$ex" 2>/dev/null || true
  done
  # 커밋 메시지 형식(타입(범위): 한국어 요약)을 검사하는 훅. 과제가 훅을 따로 쓰면 건드리지 않는다
  hk="$gd/hooks/commit-msg"
  if [ -n "$(git -C "$DST" config core.hooksPath 2>/dev/null || true)" ]; then
    hook_msg="커밋 형식 훅: 과제가 core.hooksPath를 써서 넣지 않았습니다"
  elif [ -e "$hk" ] && ! grep -qF "chocochip-codex-harness" "$hk"; then
    hook_msg="커밋 형식 훅: 과제의 commit-msg 훅이 있어 넣지 않았습니다"
  elif mkdir -p "$gd/hooks" 2>/dev/null && cp "$SRC/hooks/commit-msg" "$hk" 2>/dev/null && chmod +x "$hk" 2>/dev/null; then
    hook_msg="커밋 형식 훅: .git/hooks/commit-msg ('타입(범위): 한국어 요약'이 아니면 커밋을 막음)"
  else
    hook_msg="커밋 형식 훅: .git에 쓰지 못해 넣지 않았습니다"
  fi
fi

url="$(git -C "$SRC" remote get-url origin 2>/dev/null | sed -E 's#(://)[^/@]+@#\1#' || true)"
[ -n "$url" ] || url="주소 모름(git clone으로 받지 않음)"
rev="$(git -C "$SRC" rev-parse --short HEAD 2>/dev/null || echo "-")"
{
  echo "chocochip-codex-harness: 작업 규칙(AGENTS.md), 스킬(.agents/skills), 점검 도구(.harness/tools)."
  echo "판정 로직과 결과물은 들어 있지 않다. 과제의 판정·화면은 작업 중에 만든다."
  echo "저장소: $url"
  echo "커밋: $rev"
} > "$H/SOURCE.txt"

MARK="<!-- chocochip-codex-harness -->"
NOTE="(아래는 개인 작업 규칙이다. 이 위의 과제 AGENTS.md 내용과 다르면 위의 과제 내용을 따른다.)"
append_rules() {
  printf '\n\n%s\n' "$MARK"
  printf '%s\n\n' "$NOTE"
  cat "$SRC/AGENTS.md"
}
if [ ! -e "$DST/AGENTS.md" ]; then
  { printf '%s\n' "$MARK"; cat "$SRC/AGENTS.md"; } > "$DST/AGENTS.md"
  agents_msg="AGENTS.md를 만들었습니다."
elif grep -qxF "$MARK" "$DST/AGENTS.md"; then
  # 다시 설치하면 표시 줄 아래(하네스 규칙)만 새 내용으로 바꾸고, 위의 과제 내용은 그대로 둔다
  before="$(awk -v m="$MARK" '$0 == m { exit } { print }' "$DST/AGENTS.md")"
  if [ -z "$(printf '%s' "$before" | tr -d '[:space:]')" ]; then
    { printf '%s\n' "$MARK"; cat "$SRC/AGENTS.md"; } > "$DST/AGENTS.md.new"
  else
    { printf '%s\n' "$before"; append_rules; } > "$DST/AGENTS.md.new"
  fi
  mv "$DST/AGENTS.md.new" "$DST/AGENTS.md"
  agents_msg="AGENTS.md의 하네스 규칙 부분을 새 내용으로 바꿨습니다(그 위의 과제 내용은 그대로)."
else
  append_rules >> "$DST/AGENTS.md"
  agents_msg="과제에 있던 AGENTS.md 끝에 하네스 규칙을 덧붙였습니다(원래 내용은 그대로, 과제 내용이 우선)."
fi
size="$(wc -c < "$DST/AGENTS.md" | tr -d ' ')"
if [ "$size" -gt 32000 ]; then
  agents_msg="$agents_msg 주의: AGENTS.md가 ${size}바이트라 Codex가 32KiB 넘는 뒷부분(하네스 규칙)을 잘라 읽을 수 있습니다. \$kickoff로 시작하면 스킬이 AGENTS.md를 직접 읽습니다."
fi
rm -f "$H/INSTALLING"

retry="승인을 받아 같은 명령을 다시 실행하거나, shell 탭에서 bash $SRC/setup.sh 를 다시 실행하면 커밋됩니다(파일 설치는 끝났습니다)"
unstage() {  # 커밋이 실패하면 하네스 파일을 커밋 대기에서 뺀다(다음 작업 커밋에 섞이지 않게)
  if git -C "$DST" rev-parse --verify -q HEAD >/dev/null; then
    git -C "$DST" reset -q -- "${paths[@]}" >/dev/null 2>&1 || true
  else
    git -C "$DST" rm -r -q --cached -- "${paths[@]}" >/dev/null 2>&1 || true
  fi
}
if [ "$is_root" -eq 0 ]; then
  if git -C "$DST" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git_msg="git 저장소 맨 위($top)가 아니라서 커밋하지 않았습니다."
  else
    git_msg="git 저장소가 아니라서 커밋하지 않았습니다."
  fi
elif ! git -C "$DST" add -f -- "${paths[@]}" 2>"$ERR"; then
  git_msg="git에 넣지 못했습니다: $(first_err). Codex 샌드박스에서는 .git이 읽기 전용일 수 있습니다. $retry."
  unstage
elif git -C "$DST" diff --cached --quiet -- "${paths[@]}"; then
  git_msg="새로 커밋할 것이 없습니다(이미 설치됨)."
elif git -C "$DST" commit -q -m "chore(harness): 작업 도구 추가 ($url, $rev)" \
    -m "작업 규칙·스킬·점검 도구만 넣었다. 판정 로직과 결과물은 아니다." -- "${paths[@]}" 2>"$ERR"; then
  git_msg="하네스 파일만 따로 커밋했습니다: $(git -C "$DST" log -1 --format='%h %s')"
elif grep -qi "identity" "$ERR"; then
  unstage
  git_msg="커밋하지 못했습니다: git 사용자 이름·이메일이 없습니다. shell 탭에서 git config user.name \"이름\" && git config user.email \"메일\" 뒤 bash $SRC/setup.sh 를 다시 실행하세요(파일 설치는 끝났고, 하네스 파일은 커밋 대기에서 뺐습니다)."
else
  unstage
  git_msg="커밋하지 못했습니다: $(first_err). 원인 후보는 .git 읽기 전용, 커밋 훅, 서명 설정입니다. 하네스 파일은 커밋 대기에서 뺐습니다. $retry."
fi

# 설치한 도구가 이 환경에서 도는지 바로 본다(임시 폴더에서만 돈다). 실패해도 파일 설치는 끝난 상태다
if st="$(bash "$H/tools/selftest.sh" 2>&1)"; then st_ok=1; else st_ok=0; fi
self_msg="자체 점검(bash .harness/tools/selftest.sh): $(printf '%s\n' "$st" | tail -n 1)"
if [ "$st_ok" -eq 0 ]; then
  fails="$(printf '%s\n' "$st" | grep '^FAIL' || true)"
  if [ -n "$fails" ]; then
    self_msg="$self_msg. 실패한 도구는 쓰지 않는다(원인은 위 명령을 직접 실행하면 FAIL 아래에 나온다):
$fails"
  fi
fi

cat <<EOF
완료: $DST
- $agents_msg
- git: $git_msg
- $self_msg
- 스킬(부를 때만 동작):
    \$kickoff   과제를 받았을 때. 환경·README·데이터 점검, 요구 확인표, 담당자 첫 질문
    \$relay     담당자 답을 붙여 넣을 때. 기록, 다음 확인, 합의되면 개발 시작 메모
    \$verify    핵심 결과가 갖춰진 중간 점검(그 뒤 코드·데이터가 바뀌면 제출 전 한 번 더). 새 에이전트가 따로 계산, 행 대조, curl
    \$wrapup    마감할 때. 요건 대조, 새 에이전트 검토, 제출 문서, 키·개인정보 점검
    \$weakness  \$wrapup 뒤. 남은 약점, 한 화면 요약, 설명 점검
- 도구: .harness/tools/ (env_check, profile_data, join_check, reconcile, precheck, selftest.sh)
- 금지 규칙: .codex/rules/chocochip-codex-harness.rules (git push·원격 추가·gh·--no-verify 커밋을 막음. 커밋은 승인 창에서 y)
- $cfg_msg
- $hook_msg
- 치트시트: cat .harness/cheatsheet.md
다음:
- codex를 아직 안 켰으면 이 폴더에서 codex를 켠다.
- Codex 안에서 설치했으면 /new 를 친다. 스킬과 금지 규칙은 새 세션부터 적용된다. 어디서 실행할지 묻는 창이 뜨면 1(Use current Git worktree)을 고른다.
- "\$kickoff 남은 시간 <남은 시간>. 내가 읽은 목표: <한 줄>"로 시작한다(\$kickoff 까지 치면 목록에 뜬다).
EOF
