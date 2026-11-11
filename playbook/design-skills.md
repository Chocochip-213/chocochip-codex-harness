# 화면을 다듬을 때 쓸 수 있는 공개 스킬 (선택)

하네스에 들어 있지 않다. 필요할 때만 과제 폴더에 따로 받아 쓴다.
화면을 처음 만드는 일은 `$screen`이 한다. 아래 스킬은 **첫 판이 끝까지 돈 뒤** 모양을 다듬거나 점검할 때만 쓴다.
이 하네스와 함께 돌려 확인한 적은 없다(2026-11-11에 저장소와 파일만 확인).

## 한눈에

| 이름 | 쓰는 곳 | 저장소 (별) |
|---|---|---|
| `unslop` | 업무 화면에서 AI가 만든 티(번쩍이는 효과, 이모지 이름표, 들쭉날쭉한 간격, 과장된 문구)를 걷어 내고 다듬기. 대시보드 예시가 들어 있다 | heydamir/unslop (약 1.4만) |
| `anti-ui-slop` | 화면 점검(빠진 상태, 어디서나 본 듯한 모양)과 대시보드 다듬기. 과제 요구와 이미 있는 화면을 먼저 따른다고 적혀 있다 | github/awesome-copilot (저장소 전체 약 4.1만) |
| `frontend-design` | 발표용 HTML처럼 인상이 중요한 화면 | anthropics/skills (저장소 전체 약 19만) |

하나만 받는다면 업무 화면에는 `unslop`, 발표용 HTML에는 `frontend-design`.

## 받는 법

하네스를 설치한 뒤 과제 폴더 맨 위에서 실행한다. 받은 다음 Codex에서 `/new`를 치고 `$이름`을 쳐서 목록에 뜨는지 본다.

```bash
git clone --depth 1 https://github.com/heydamir/unslop /tmp/us && mkdir -p .agents/skills && cp -r /tmp/us/skills/unslop .agents/skills/
```

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/github/awesome-copilot /tmp/ac && git -C /tmp/ac sparse-checkout set skills/anti-ui-slop && mkdir -p .agents/skills && cp -r /tmp/ac/skills/anti-ui-slop .agents/skills/
```

```bash
git clone --depth 1 https://github.com/anthropics/skills /tmp/as && mkdir -p .agents/skills/frontend-design && cp /tmp/as/skills/frontend-design/* .agents/skills/frontend-design/
```

받은 스킬 폴더는 커밋하지 않아도 된다.

## 쓰는 말

먼저 고칠 곳을 목록으로만 받는다.

- "$unslop 지금 화면에서 AI가 만든 티가 나는 곳을 큰 것부터 다섯 개만 목록으로 보여 줘. 아직 고치지 마."
- "$anti-ui-slop 지금 화면을 점검만 해 줘. 빠진 상태(빈 결과, 오류, 불러오는 중)와 어디서나 본 듯한 곳을 큰 것부터 다섯 개만. 고치지는 마. 외부 주소는 열지 말고 폴더 안 문서만 써."

그다음 내가 고른 것만 이유와 함께 고치게 한다.

- "1번과 3번만 고쳐 줘. <이유 한 마디>. 계산과 판정, 화면에 보이는 정보는 그대로 둬. 외부 글꼴과 외부 파일은 쓰지 마. 끝나면 800과 1280 폭에서 찍어 보여 줘."

발표용 HTML:

- "$frontend-design 발표용 HTML을 파일 하나로 만들어 줘. 외부 글꼴과 외부 파일 없이 열리게. 숫자는 결정 기록과 검증 보고에 있는 것만 써. 문장은 내가 고칠 거니까 짧게."

## 꼭 붙일 조건

- 계산·판정과 화면에 보이는 정보는 그대로 둔다. 바꾸는 것은 모양뿐이다.
- 외부 글꼴과 외부 파일(CDN)은 쓰지 않는다. 미리보기에서 막히면 화면이 깨진다.
- 읽기 쉬운 것이 먼저다. 화려해져서 읽기 어려워지면 "screen 스킬 기준으로 되돌려 줘".
- 스킬에 딸린 스크립트(Node)가 안 돌면 건너뛰고 `.harness/tools/ui_check.py`로 찍게 한다.
- 긴 스킬이다(`unslop`은 본문만 3만 바이트). 한 대화에서 한 번만 부르고, 다듬기 단계는 새 대화에서 한다.
- 다듬은 뒤 화면을 내가 직접 다시 눌러 본다. 값이나 버튼이 사라졌으면 되돌리게 한다.

## 지우는 법

화면이 이상해지면 폴더를 지우고 `/new`를 친다.

```bash
rm -rf .agents/skills/unslop .agents/skills/anti-ui-slop .agents/skills/frontend-design
```

## 라이선스

- `unslop`: CC BY 4.0. 만든 사람(Damir Sokolovsky) 표시를 지우지 않는다.
- `anti-ui-slop`: MIT.
- `frontend-design`: 폴더의 `LICENSE.txt`를 따른다.
