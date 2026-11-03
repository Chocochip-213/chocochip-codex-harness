#!/usr/bin/env python3
"""화면 점검: 실제 브라우저(Playwright Chromium)로 주소를 여러 폭에서 열어 PNG로 찍고, 읽기를 막는 배치 문제를 DOM에서 센다.

사용:
  python3 ui_check.py http://localhost:8000/ --out /tmp/ui_check/home
  python3 ui_check.py http://localhost:8000/list --widths 760,1280 --ready "table tbody tr"
  # 로그인이 필요한 화면: 앱의 정상 로그인 폼을 거친다(계정 값은 실행 안내의 환경 파일에서 읽어 환경변수 이름으로만 넘긴다.
  # 값을 명령줄에 직접 쓰지 않는다. 명령줄은 세션 기록에 남는다)
  (set -a; . ./.env; set +a; python3 ui_check.py http://localhost:8000/admin/ \\
      --login-url http://localhost:8000/login/ --user-env APP_USER --pass-env APP_PASS --save-state /tmp/ui_check/state.json)
  python3 ui_check.py http://localhost:8000/admin/ --storage-state /tmp/ui_check/state.json

- 폭마다 <out>/w<폭>.png(첫 화면. --full-page면 페이지 전체)와 <out>/report.json을 만든다.
- report.json의 폭별 항목과 뜻:
    page_overflow    페이지가 가로로 넘친 픽셀(0이어야 한다. 넘치면 가로 스크롤이 페이지 전체에 생긴다)
    to_login         요청한 화면 대신 로그인 화면으로 돌아갔으면 1(그 화면을 본 것이 아니다)
    redirected       요청한 주소와 다른 주소로 열렸으면 1(정보. 첫 화면으로 가는 설계된 이동일 수 있다. final_url에 실제 주소)
    offscreen        화면 밖으로 나간 요소 수(안에서 가로 스크롤하는 표 감싸개 속 요소는 세지 않는다)
    clipped          글자가 잘린 요소 수(overflow hidden인데 내용이 더 넓거나 높고 말줄임·줄 수 제한도 없음)
    ellipsis         말줄임(…)으로 줄여진 요소 수(핵심 근거를 숨기고 있지 않은지 본다)
    unlabeled_inputs 이름표(label·aria-label·title) 없는 입력 수
    console_errors   콘솔 오류·페이지 오류 수(파일을 못 읽은 오류는 failed_requests에만 센다)
    failed_requests  실패한 요청 수(CSS·JS가 안 읽힌 것 포함). 브라우저가 스스로 요청한 탭 아이콘의 404는 ignored_requests에
                     정보로만 남긴다(그것을 없애려고 라우트를 더하지 않는다)
    scrollers        안에서 가로 스크롤하는 영역(표 감싸개 등)의 내용 폭/보이는 폭. 문제 건수에는 넣지 않는다.
                     내용 폭이 보이는 폭보다 훨씬 크면 핵심 열(근거 등)이 스크롤 밖에 숨어 있지 않은지 PNG로 본다
  항목마다 예시 요소(태그#id.class "글자 앞부분")를 다섯 개까지 적는다.
- 폭 기본값 800,1280: IDE 안 미리보기 창 안팎과 넓은 창. 실제 폭을 알면 그 값을 쓴다.
- Playwright나 브라우저가 없으면 설치 명령을 안내하고 종료 2. 리눅스면 그 전에 브라우저가 쓰는 시스템 라이브러리가 있는지 먼저 보여 준다.
- 리눅스에서 시스템 라이브러리가 없으면 Playwright가 알려 주는 빠진 패키지 중 라이브러리만 `apt-get download`로 받아
  ~/.cache/ui_check에 풀고 그 경로로 브라우저를 켠다(관리자 권한 없이. 처음 한 번 10MB 안팎). 받지 못하면 하네스 vendor/ui_check의
  우분투 22.04용 예비 라이브러리를 쓴다. 한글 글꼴이 없으면 화면이 네모(□)로 찍히므로 vendor/ui_check의 나눔고딕을
  ~/.local/share/fonts/ui_check에 둔다. 어느 쪽이든 무엇을 했는지 한 줄로 알린다.
    설치: python3 -m pip install playwright && python3 -m playwright install --only-shell chromium(지금 권한에서 네트워크가 막혀 있으면 승인을 받아 샌드박스 밖에서)
    이미 설치된 Chrome·Edge가 있으면 브라우저 내려받기 대신 --channel chrome 또는 --channel msedge 를 쓴다.
- 종료 코드: 0 문제 없음, 1 문제 있음(개수는 report.json), 2 Playwright·브라우저 없음, 3 사용법·접속·실행 오류.
- 로그인 상태 파일(--save-state)과 PNG는 커밋하지 않는다. 인증을 우회하지 않는다. 입력칸의 값, 주소의 계정 정보·물음표·# 뒤,
  로그인에 쓴 계정 값은 기록·출력하지 않는다.
- 로그인 뒤에도 비밀번호 칸이 보이면 로그인되지 않은 것으로 보고 종료 3. 로그인 상태는 목표 화면에 실제로 도착한 것을 본 뒤에만
  저장한다. 목표 화면인지 확실히 하려면 --ready에 그 화면에만 있는 요소(앱 코드에서 확인)를 준다.
- 실패하면 report.json을 남기지 않는다(지난 결과도 지운다).
- PNG를 만들었다고 본 것이 아니다. 이미지 보기 도구로 열어 보고, report.json의 예시 요소와 함께 고칠 곳을 정한다.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

INSTALL_HINT = (
    "Playwright가 없습니다. 가상환경에 설치했으면 그 파이썬(예: .venv/bin/python)으로 이 도구를 실행한다. 설치(지금 권한에서 네트워크가 막혀 있으면 승인을 받아 샌드박스 밖에서): python3 -m pip install playwright && python3 -m playwright install --only-shell chromium\n"
    "(pip가 막혀 있으면 설치하지 않고, 사용자가 IDE 브라우저에서 실제 폭으로 보고 어느 영역이 어떻게 보이는지 말해 주는 방식으로 대신한다)"
)
BROWSER_HINT = (
    "브라우저를 켤 수 없습니다. 아래 원인을 보고 하나만 시도한다:\n"
    "- 실행 파일이 없다는 원인: python3 -m playwright install --only-shell chromium\n"
    "- 공유 라이브러리(.so)가 없다는 원인: 위 '시스템 라이브러리' 줄을 본다(사용자 폴더에 받지 못했으면 그 이유가 있다). 관리자 권한이 있으면 python3 -m playwright install-deps chromium\n"
    "- 이미 설치된 Chrome·Edge가 있으면 --channel chrome 또는 --channel msedge\n"
    "설치 시도 시간이 다 됐거나 지금 권한으로 안 되면 사용자가 실제 폭으로 보고 말해 주는 방식으로 넘어간다."
)

MEASURE_JS = r"""
() => {
  const doc = document.documentElement;
  const vw = doc.clientWidth;
  const body = document.body;
  const pageOverflow = Math.max(0, Math.max(doc.scrollWidth, body ? body.scrollWidth : 0) - vw);
  const desc = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    if (el.classList && el.classList.length) s += '.' + Array.from(el.classList).slice(0, 3).join('.');
    const tag = el.tagName.toLowerCase();
    if (tag === 'input' || tag === 'select' || tag === 'textarea') {  // 입력값은 적지 않는다(계정 값이 기록에 남지 않게)
      const t = el.getAttribute('type'), n = el.getAttribute('name');
      return s + (t ? '[type=' + t + ']' : '') + (n ? '[name=' + n + ']' : '');
    }
    const raw = (el.innerText || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ')
      .replace(/\b0\d{1,2}-\d{3,4}-\d{4}\b/g, '<전화>').replace(/[\w.%+-]+@[\w.-]+/g, '<메일>');  // 기록에 개인정보 모양을 남기지 않는다
    return raw ? s + ' "' + raw.slice(0, 40) + '"' : s;
  };
  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const inScroller = (el) => {  // 안에서 가로 스크롤하는 조상(표 감싸개 등)이 있으면 설계된 넘침으로 본다
    for (let a = el.parentElement; a && a !== body; a = a.parentElement) {
      const ox = getComputedStyle(a).overflowX;
      if ((ox === 'auto' || ox === 'scroll') && a.scrollWidth > a.clientWidth + 1) return true;
    }
    return false;
  };
  const offscreen = [], clipped = [], ellipsis = [], scrollers = [];
  const all = body ? Array.from(body.querySelectorAll('*')) : [];
  for (const el of all) {
    if (!visible(el)) continue;
    const sx = getComputedStyle(el).overflowX;
    if ((sx === 'auto' || sx === 'scroll') && el.scrollWidth > el.clientWidth + 1)
      scrollers.push(desc(el).slice(0, 60) + ' 내용 ' + el.scrollWidth + 'px / 보이는 ' + el.clientWidth + 'px');
    const r = el.getBoundingClientRect();
    const srOnly = r.width <= 1 && r.height <= 1 && ['absolute', 'fixed'].includes(getComputedStyle(el).position);  // 화면 읽기용으로 숨긴 1px 글자
    if ((r.right > vw + 1 || r.left < -1) && !inScroller(el) && !srOnly) {
      if (!offscreen.some(o => o.contains(el))) offscreen.push(el);  // 부모가 이미 잡혔으면 자식은 세지 않는다
    }
    const cs = getComputedStyle(el);
    const ox = cs.overflowX, oy = cs.overflowY;
    const cutX = (ox === 'hidden' || ox === 'clip') && el.scrollWidth > el.clientWidth + 1;
    const cutY = (oy === 'hidden' || oy === 'clip') && el.scrollHeight > el.clientHeight + 2 && (el.innerText || '').trim() !== '';
    if ((cutX || cutY) && !srOnly) {  // 말줄임(…)과 줄 수 제한은 의도한 줄임으로 따로 센다
      const clamp = cs.webkitLineClamp && cs.webkitLineClamp !== 'none';
      if ((cutX && cs.textOverflow === 'ellipsis') || (!cutX && clamp)) ellipsis.push(el); else clipped.push(el);
    }
  }
  const unlabeled = [];
  for (const el of document.querySelectorAll('input, select, textarea')) {
    const type = (el.getAttribute('type') || '').toLowerCase();
    if (['hidden', 'submit', 'button', 'reset', 'image'].includes(type)) continue;
    if (!visible(el)) continue;
    const lb = (el.getAttribute('aria-labelledby') || '').split(/\s+/)
      .some(id => { const t = id && document.getElementById(id); return t && t.textContent.trim(); });  // 가리키는 대상에 글자가 있어야 이름표
    const named = (s) => !!(s && s.trim());
    const ok = (el.labels && Array.from(el.labels).some(l => named(l.textContent))) || named(el.getAttribute('aria-label')) || lb
      || (el.closest('label') && named(el.closest('label').textContent)) || named(el.getAttribute('title'));
    if (!ok) unlabeled.push(el);
  }
  const ex = (arr) => arr.slice(0, 5).map(desc);
  return {
    viewport_width: vw, document_height: doc.scrollHeight, page_overflow: pageOverflow,
    offscreen: offscreen.length, offscreen_examples: ex(offscreen),
    clipped: clipped.length, clipped_examples: ex(clipped),
    ellipsis: ellipsis.length, ellipsis_examples: ex(ellipsis),
    unlabeled_inputs: unlabeled.length, unlabeled_examples: ex(unlabeled),
    scrollers: scrollers.slice(0, 5),
  };
}
"""

PROBLEM_KEYS = ("page_overflow", "to_login", "offscreen", "clipped", "unlabeled_inputs", "console_errors", "failed_requests")


SECRETS = []  # 로그인에 쓴 계정 값. 기록·출력 전에 가린다


URL_IN_TEXT = re.compile(r"https?://[^\s'\"<>]+")
EMAIL_IN_TEXT = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_IN_TEXT = re.compile(r"(?<![\d+])(\+82[-. ]?|0)(1[016789]|\d{1,2})[-. ]?\d{3,4}[-. ]?\d{4}(?!\d)")


def scrub(text):
    for s in SECRETS:
        if s:
            text = text.replace(s, "***")
    text = URL_IN_TEXT.sub(lambda m: safe_bare(m.group(0)), text)  # 오류·콘솔 글 속 주소의 토큰도 남기지 않는다
    return PHONE_IN_TEXT.sub("<전화번호>", EMAIL_IN_TEXT.sub("<이메일>", text))


def safe_bare(url):
    try:
        return bare(url)
    except ValueError:
        return "(주소)"


def bare(url):
    """기록용 주소: 계정 정보(user:pass@)와 물음표·# 뒤(토큰·값이 들 수 있음)를 뗀다. 비교에는 쓰지 않는다."""
    u = urlsplit(url)
    return f"{u.scheme}://{u.hostname or ''}{':' + str(u.port) if u.port else ''}{u.path}"


def same_place(a, b):
    """요청한 화면에 실제로 왔는지: 주소의 호스트·경로·# 뒤까지 비교한다(물음표 뒤 값은 보지 않는다)."""
    x, y = urlsplit(a), urlsplit(b)
    return (x.netloc, x.path.rstrip("/"), x.fragment) == (y.netloc, y.path.rstrip("/"), y.fragment)


def browser_icon_404(url, status):
    """브라우저가 스스로 요청한 탭 아이콘의 404는 페이지 문제가 아니다(정보로만 남긴다)."""
    return status == 404 and urlsplit(url).path == "/favicon.ico"


CORE_LIBS = ("libnss3.so", "libnspr4.so", "libatk-1.0.so", "libgbm.so", "libasound.so")  # 헤드리스 Chromium이 늘 쓰는 시스템 라이브러리


def missing_system_libs():
    """리눅스에서 브라우저를 받기 전에 시스템 라이브러리가 있는지 본다(없으면 받아도 켜지지 않는다). 알 수 없으면 None."""
    if not sys.platform.startswith("linux"):
        return None
    import shutil
    import subprocess
    ldc = shutil.which("ldconfig") or ("/sbin/ldconfig" if os.path.exists("/sbin/ldconfig") else None)
    if not ldc:
        return None
    try:
        r = subprocess.run([ldc, "-p"], capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    if r.returncode != 0 or not r.stdout.strip():  # 조회 실패는 '없음'이 아니라 '모름'
        return None
    return [lib for lib in CORE_LIBS if lib not in r.stdout]


def print_lib_check(have_playwright):
    """시스템 라이브러리가 모자라고 사용자 폴더에도 받을 수 없으면 True(브라우저 내려받기 안내를 내지 않는다)."""
    import shutil
    miss = missing_system_libs()
    if miss and shutil.which("apt-get") and shutil.which("dpkg"):
        print("시스템 라이브러리 없음: " + ", ".join(miss) + ". 실행 때 sudo 없이 ~/.cache/ui_check에 받아 쓴다(apt-get download)")
        return False
    if miss:
        fix = ("python3 -m playwright install-deps chromium" if have_playwright
               else "python3 -m pip install playwright 뒤 python3 -m playwright install-deps chromium")
        print("시스템 라이브러리 없음: " + ", ".join(miss) + ". apt-get이 없어 사용자 폴더에 받을 수 없고, 브라우저를 받아도 켜지지 않는다. "
              f"관리자 권한이 있으면 {fix}(그 뒤 브라우저 설치), 없으면 설치하지 말고 사용자가 실제 폭으로 보고 말해 주는 방식으로 넘어간다")
        return True
    if miss == []:
        print("시스템 라이브러리: 핵심 다섯 개(" + ", ".join(CORE_LIBS) + ")는 있음(다른 것이 모자라면 실행 때 원인에 나온다)")
    elif sys.platform.startswith("linux"):
        print("시스템 라이브러리: 확인하지 못함(ldconfig 조회 실패)")
    return False


USER_CACHE = Path.home() / ".cache" / "ui_check"  # sudo 없이 받은 패키지. 홈이 작업 폴더면 설치기가 점 폴더를 git 제외에 넣는다(폴더째 제출할 때는 따로 뺀다)
_SRC_BUNDLE = Path(__file__).resolve().parent.parent / "vendor" / "ui_check"  # 하네스 저장소 안에서 돌릴 때
BUNDLE = _SRC_BUNDLE if _SRC_BUNDLE.is_dir() else USER_CACHE / "bundle"  # 설치기가 커밋 밖에 둔 글꼴·예비 라이브러리
SETUP_SECONDS = 180  # 라이브러리 받기 전체 상한(screen 스킬의 '도구 설치 시도 3분')


def run_quiet(cmd, timeout, cwd=None):
    """명령을 조용히 돌린다. (결과 또는 None, 실패 사유 한 줄)"""
    import subprocess
    if timeout <= 0:
        return None, "시간 상한을 다 씀"
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd), ""
    except subprocess.TimeoutExpired:
        return None, f"{cmd[0]}이 {timeout:.0f}초 안에 끝나지 않음"
    except OSError as e:
        return None, f"{cmd[0]} 실행 못 함({e.strerror})"


def lib_dirs(root):
    return [str(p) for p in sorted(root.glob("usr/lib/*-linux-gnu")) + sorted(root.glob("lib/*-linux-gnu"))]


def has_libs(dirs, need):
    """need(빠진 .so 이름 앞부분)가 dirs 어딘가에 모두 실제 파일로 있나"""
    return bool(dirs) and all(any(f.is_file() for d in dirs for f in Path(d).glob(lib + "*")) for lib in need)


def installed(name, deadline):
    import time
    r, _ = run_quiet(["dpkg-query", "-W", "-f=${Status}", name], min(10, deadline - time.monotonic()))
    return r is not None and r.returncode == 0 and "install ok installed" in r.stdout


def fetch_libs(root, deadline):
    """Playwright가 이 배포판 이름으로 알려 준 빠진 패키지 중 라이브러리만 받아 root에 푼다. (푼 이름, 마지막 실패 사유)"""
    import re
    import time
    r, why = run_quiet([sys.executable, "-m", "playwright", "install-deps", "--dry-run", "chromium"],
                       min(60, deadline - time.monotonic()))
    if r is None:
        return [], "빠진 패키지 목록을 못 얻음(" + why + ")"
    text = r.stdout + r.stderr
    head = re.search(r"Missing system dependencies[^\n]*\n((?:[ \t]+\S+[ \t]*(?:\n|$))+)", text)  # 이 머리말 아래 목록만 읽는다
    if head:
        names = re.findall(r"^\s+(lib[a-z0-9.+-]*(?::[a-z0-9]+)?)\s*$", head.group(1), re.M)
    else:  # 판에 따라 설치 명령 한 줄로 알려 준다(이미 있는 것도 들어 있다)
        m = re.search(r"--no-install-recommends ([a-z0-9.+:\- ]+)", text)
        names = [n for n in (m.group(1).split() if m else []) if n.startswith("lib")]
    names = [n for n in names if not installed(n, deadline)]  # 글꼴·가상 화면 서버는 헤드리스 찍기에 필요 없어 lib만 본다
    if not names:
        return [], "빠진 라이브러리 패키지 이름을 알 수 없음"
    import shutil
    got, fail = [], ""
    for name in names:
        deb = USER_CACHE / "deb" / name.replace(":", "_")  # 패키지마다 빈 폴더에 받아 이번에 받은 파일만 푼다
        shutil.rmtree(deb, ignore_errors=True)
        deb.mkdir(parents=True, exist_ok=True)
        r, why = run_quiet(["apt-get", "-o", "Acquire::http::Timeout=10", "-o", "Acquire::https::Timeout=10",
                            "-o", "Acquire::Retries=0", "download", name], min(60, deadline - time.monotonic()), cwd=deb)
        if r is None:
            return got, why  # 시간 상한·실행 불가면 나머지도 받지 않는다
        files = list(deb.glob("*.deb"))
        if r.returncode != 0 or len(files) != 1:
            last = (r.stderr.strip().splitlines() or [""])[-1]
            fail = f"apt-get download {name} 실패(종료 {r.returncode}" + (f": {scrub(last)[:120]}" if last else "") + ")"
            continue
        x, why = run_quiet(["dpkg", "-x", str(files[0]), str(root)], deadline - time.monotonic())
        if x is None or x.returncode != 0:
            fail = why or f"dpkg -x {name} 실패(종료 {x.returncode})"
            continue
        got.append(name)
    return got, fail


def user_lib_path(need):
    """need를 채우는 LD_LIBRARY_PATH 값: 사용자 폴더에 받은 것, 모자라면 하네스 예비 라이브러리까지. 못 채우면 None."""
    import platform
    import shutil
    import time
    root = USER_CACHE / "root"
    dirs = lib_dirs(root)
    if not has_libs(dirs, need):  # 폴더가 있어도 필요한 파일이 없으면 다시 받는다
        if os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED"):
            print("시스템 라이브러리: 샌드박스가 네트워크를 막아 받지 않음(승인받아 다시 실행하면 받는다)")
        elif shutil.which("apt-get") and shutil.which("dpkg"):
            got, why = fetch_libs(root, time.monotonic() + SETUP_SECONDS)
            dirs = lib_dirs(root)
            if got:
                print(f"시스템 라이브러리: sudo 없이 {USER_CACHE}에 받음(" + ", ".join(got) + ")")
            if not has_libs(dirs, need):
                print("시스템 라이브러리: 사용자 폴더에 다 받지 못함(" + (why or "받은 것에 필요한 파일이 없음") + ")")
        else:
            print("시스템 라이브러리: apt-get·dpkg가 없어 사용자 폴더에 받지 못함")
    if has_libs(dirs, need):
        return ":".join(dirs)
    pre = BUNDLE / "libs-ubuntu22.04-amd64"
    both = dirs + [str(pre), str(pre / "nss")]
    if pre.is_dir() and platform.machine() in ("x86_64", "AMD64") and has_libs(both, need):
        print("시스템 라이브러리: 하네스의 예비 라이브러리(우분투 22.04 amd64용)를 씀. 이 컴퓨터의 판과 맞지 않으면 브라우저가 켜지지 않고 원인 줄에 나온다")
        return ":".join(both)
    print("시스템 라이브러리: 맞는 예비 라이브러리도 없음(" + ", ".join(need) + ")")
    return None


def ensure_korean_font():
    """한글 글꼴이 없으면 화면이 네모(□)로 찍혀 읽을 수 없다. 하네스의 나눔고딕을 사용자 글꼴 폴더에 둔다."""
    import shutil
    if shutil.which("fc-list"):
        r, why = run_quiet(["fc-list", ":lang=ko"], 20)
        if r is not None and r.returncode == 0 and r.stdout.strip():
            return
    fonts = sorted((BUNDLE / "fonts").glob("*.ttf"))
    if not fonts:
        print("한글 글꼴 없음: 하네스의 글꼴 파일도 없어 한글이 네모(□)로 찍힐 수 있다. 글자는 본문·report.json으로 본다")
        return
    dest = Path.home() / ".local" / "share" / "fonts" / "ui_check"
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for f in fonts:
            shutil.copy2(f, dest / f.name)
    except OSError as e:
        print(f"한글 글꼴: {dest}에 두지 못함({e.strerror}). 한글이 네모(□)로 찍힐 수 있다")
        return
    c, why = run_quiet(["fc-cache", "-f", str(dest)], 60) if shutil.which("fc-cache") else (None, "fc-cache 없음")
    ok = c is not None and c.returncode == 0
    print(f"한글 글꼴: 하네스의 나눔고딕을 {dest}에 둠" + ("" if ok else "(fc-cache 실패: " + (why or "종료 코드 0 아님") + ". 한글이 네모로 찍힐 수 있다)"))


def cause_lines(e, n=6):
    """오류 메시지에서 상자 테두리를 걷고 내용 있는 줄을 n개(라이브러리를 못 읽은 줄을 먼저. 첫 줄만으로는 원인이 안 보일 때가 있다)."""
    out = []
    for x in str(e).splitlines():
        x = x.strip(" ║╔╗╚╝═|─")
        if x and x not in ("BrowserType.launch:",):
            out.append(x)
    key = [x for x in out if ".so" in x or "shared librar" in x]
    return (key + [x for x in out if x not in key])[:n] or [type(e).__name__]


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"요약: 종료 3, 사용법 오류: {message}")
        sys.exit(3)


def parse_args(argv):
    p = Parser(description="실제 브라우저로 화면을 여러 폭에서 찍고 배치 문제를 센다", add_help=False)
    p.add_argument("url", help="열 주소(사람이 실제로 여는 주소. 미리보기 경로가 있으면 그 주소)")
    p.add_argument("-h", "--help", action="help", help="이 도움말")
    p.add_argument("--widths", default="800,1280", help="쉼표로 나눈 폭(px). 기본 800,1280")
    p.add_argument("--height", type=int, default=900, help="창 높이(px). 기본 900")
    p.add_argument("--out", default="/tmp/ui_check", help="PNG와 report.json을 둘 폴더. 기본 /tmp/ui_check")
    p.add_argument("--ready", help="이 CSS 선택자가 나타날 때까지 기다린 뒤 찍는다(예: 'table tbody tr')")
    p.add_argument("--timeout", type=int, default=15000, help="기다리는 최대 ms. 기본 15000")
    p.add_argument("--full-page", action="store_true", help="첫 화면만이 아니라 페이지 전체를 찍는다")
    p.add_argument("--channel", help="설치된 브라우저로 켠다: chrome, msedge 등")
    p.add_argument("--login-url", help="앱의 로그인 화면 주소. 아래 환경변수의 값으로 폼을 채우고 제출한 뒤 url을 연다")
    p.add_argument("--user-env", help="아이디 값을 담은 환경변수 이름(값은 출력하지 않는다)")
    p.add_argument("--pass-env", help="비밀번호 값을 담은 환경변수 이름(값은 출력하지 않는다)")
    p.add_argument("--user-selector", default='input[type="email"]|input[name*="user" i]|input[name*="login" i]|input[name*="id" i]|input[type="text"]',
                   help="아이디 칸 선택자. '|'로 나눈 후보를 차례로 보고 보이는 첫 칸을 쓴다. 앱의 로그인 폼 코드를 보고 정확히 주는 것이 좋다")
    p.add_argument("--pass-selector", default='input[type="password"]', help="비밀번호 칸 선택자('|'로 나눈 후보를 차례로)")
    p.add_argument("--submit-selector", default='button[type="submit"]|input[type="submit"]|form button', help="로그인 버튼 선택자('|'로 나눈 후보를 차례로)")
    p.add_argument("--storage-state", help="저장해 둔 로그인 상태 파일을 읽어 쓴다")
    p.add_argument("--save-state", help="로그인 뒤 상태를 이 파일에 저장한다(커밋하지 않는다)")
    return p.parse_args(argv)


def widths_of(text):
    out = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit() or int(part) < 200:
            print(f"요약: 종료 3, 사용법 오류: 폭은 200 이상의 정수여야 함: {part!r}")
            sys.exit(3)
        out.append(int(part))
    if not out:
        print("요약: 종료 3, 사용법 오류: 폭이 없음")
        sys.exit(3)
    return out


def first_visible(page, selectors, what):
    """'|'로 나눈 후보를 차례로 보고 보이는 첫 요소를 고른다(문서 순서가 아니라 후보 순서)."""
    for sel in selectors.split("|"):
        loc = page.locator(sel.strip())
        for i in range(loc.count()):
            if loc.nth(i).is_visible():
                return loc.nth(i)
    raise RuntimeError(f"{what}을 찾지 못함(선택자: {selectors})")


def any_visible(page, selectors):
    for sel in selectors.split("|"):
        loc = page.locator(sel.strip())
        if any(loc.nth(i).is_visible() for i in range(loc.count())):
            return True
    return False


def same_path(a, b):
    return urlsplit(a).path.rstrip("/") == urlsplit(b).path.rstrip("/")


def login(page, args, timeout):
    """앱의 정상 로그인 폼을 거친다. 로그인됐는지 확인하지 못하면 실행 오류로 끝낸다(로그인 화면을 검사한 결과를 성공으로 쓰지 않게)."""
    user = os.environ.get(args.user_env or "")
    pw = os.environ.get(args.pass_env or "")
    if not args.user_env or not args.pass_env or user is None or pw is None:
        raise RuntimeError("--login-url에는 --user-env와 --pass-env(값이 든 환경변수 이름)가 필요함")
    SECRETS.extend([user, pw])
    page.goto(args.login_url, wait_until="load", timeout=timeout)
    first_visible(page, args.user_selector, "아이디 칸").fill(user, timeout=timeout)
    first_visible(page, args.pass_selector, "비밀번호 칸").fill(pw, timeout=timeout)
    first_visible(page, args.submit_selector, "로그인 버튼").click(timeout=timeout)
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass
    if any_visible(page, args.pass_selector):
        if same_path(page.url, args.login_url):
            raise RuntimeError("로그인 뒤에도 로그인 화면에 비밀번호 칸이 보임. 로그인되지 않은 것으로 보고 멈춤(선택자·계정 값 확인)")
        print(f"주의: 로그인 뒤 다른 화면({bare(page.url)})에도 비밀번호 칸이 있음. 목표 화면 도착 여부로 판단한다")


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    out = Path(args.out)
    report_path = out / "report.json"
    try:
        report_path.unlink(missing_ok=True)  # 이번에 실패하면 지난 결과가 이번 결과로 읽히지 않게(어느 실패 경로든)
    except OSError as e:
        print(f"요약: 종료 3, 실행 오류: 지난 report.json을 지우지 못함({e}). 그 파일은 이번 결과가 아니다")
        return 3
    widths = widths_of(args.widths)
    try:
        urlsplit(args.url).port  # 포트 오타 같은 주소 오류를 여기서 잡는다
        if args.login_url:
            urlsplit(args.login_url).port
    except ValueError as e:
        print(f"요약: 종료 3, 사용법 오류: 주소가 잘못됨({e})")
        return 3
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("요약: 종료 2, Playwright 없음")
        if not print_lib_check(have_playwright=False):  # 설치(수백 MB) 전에 켜질 수 있는 컴퓨터인지 먼저 본다
            print(INSTALL_HINT)
        return 2
    if args.height < 200 or args.timeout < 1000:
        print("요약: 종료 3, 사용법 오류: --height는 200 이상, --timeout은 1000(ms) 이상")
        return 3
    if args.storage_state and not Path(args.storage_state).exists():
        print(f"요약: 종료 3, 실행 오류: 상태 파일 없음: {args.storage_state}")
        return 3
    report = {"url": bare(args.url), "height": args.height, "widths": {}}
    console_errors, failed, ignored = [], {}, {}  # failed는 주소마다 한 번만 센다
    launch_kw = {"channel": args.channel} if args.channel else {}
    tried_libs = False
    if sys.platform.startswith("linux"):
        try:
            ensure_korean_font()
            need = missing_system_libs()
            path = user_lib_path(need) if need else None
        except Exception as e:  # 준비가 깨져도 요약 줄과 종료 코드는 지킨다
            print(f"요약: 종료 3, 실행 오류: 화면 점검 준비 실패({type(e).__name__}: {scrub(str(e))[:200]})")
            return 3
        tried_libs = bool(need)
        if path:  # 브라우저와 Playwright의 사전 검사(ldd)가 같은 경로를 보게 이 프로세스 환경에 둔다
            old = os.environ.get("LD_LIBRARY_PATH")
            os.environ["LD_LIBRARY_PATH"] = path + (":" + old if old else "")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(**launch_kw)
        except Exception as e:
            print("요약: 종료 2, 브라우저를 켜지 못함")
            if tried_libs:
                print("시스템 라이브러리: 위에서 둔 경로로도 켜지지 않음(아래 원인 줄의 .so 이름을 본다)")
                print(BROWSER_HINT)
            elif not print_lib_check(have_playwright=True):
                print(BROWSER_HINT)
            print("원인: " + " / ".join(cause_lines(e)))
            return 2
        try:
            out.mkdir(parents=True, exist_ok=True)
            ctx_kw = {"viewport": {"width": widths[0], "height": args.height}}
            if args.storage_state:
                ctx_kw["storage_state"] = args.storage_state
            context = browser.new_context(**ctx_kw)
            page = context.new_page()
            # 파일을 못 읽은 콘솔 오류는 실패 요청과 같은 일이라 한 번만 센다. 기록 전에 계정 값을 가린다
            page.on("console", lambda m: console_errors.append(scrub(m.text)[:200])
                    if m.type == "error" and not m.text.startswith("Failed to load resource") else None)
            page.on("pageerror", lambda e: console_errors.append(scrub(str(e))[:200]))
            page.on("requestfailed", lambda r: failed.setdefault(r.url, f"{bare(r.url)} ({r.failure})"))
            page.on("response", lambda r: (ignored if browser_icon_404(r.url, r.status) else failed).setdefault(
                r.url, f"{bare(r.url)} (HTTP {r.status})") if r.status >= 400 else None)
            if args.login_url:
                login(page, args, args.timeout)
            for w in widths:
                console_errors.clear()
                failed.clear()
                ignored.clear()
                page.set_viewport_size({"width": w, "height": args.height})
                response = page.goto(args.url, wait_until="load", timeout=args.timeout)
                if args.ready:
                    page.wait_for_selector(args.ready, timeout=args.timeout)
                else:
                    try:
                        page.wait_for_load_state("networkidle", timeout=min(args.timeout, 5000))
                    except Exception:
                        pass
                m = page.evaluate(MEASURE_JS)
                m["document_status"] = response.status if response is not None else None
                for k in [k for k in m if k.endswith("_examples")] + ["scrollers"]:
                    m[k] = [scrub(x) for x in m.get(k, [])]  # 화면 글자에 계정 값이 보여도 기록에는 남기지 않는다
                png = out / f"w{w}.png"
                page.screenshot(path=str(png), full_page=args.full_page, timeout=args.timeout)
                # 요청한 주소와 실제로 열린 주소가 다르면(로그인 화면으로 돌려보내짐 등) 그 화면을 본 것이 아니다
                m["final_url"] = bare(page.url)
                m["redirected"] = int(not same_place(page.url, args.url))  # 정보: 설계된 이동(첫 화면으로 등)일 수 있다
                # 문제: 로그인 화면으로 돌아감(그 화면을 본 것이 아니다)
                checking_login = bool(args.login_url) and same_path(args.url, args.login_url)  # 로그인 화면 자체를 점검할 때만 예외
                on_login = (bool(args.login_url) and same_path(page.url, args.login_url)) or (
                    not args.ready and any_visible(page, args.pass_selector))  # 목표 화면 표시가 확인되면 비밀번호 칸만으로 판정하지 않는다
                want_auth = bool(args.login_url or args.storage_state)  # 로그인한 화면을 기대하면 주소가 같아도 로그인 화면이면 문제
                m["to_login"] = int(not checking_login and on_login and (want_auth or bool(m["redirected"])))
                m["console_errors"] = len(console_errors)
                m["console_examples"] = console_errors[:5]
                m["failed_requests"] = len(failed)
                m["failed_examples"] = list(failed.values())[:5]
                m["ignored_requests"] = list(ignored.values())[:5]
                m["png"] = str(png)
                report["widths"][str(w)] = m
            # 로그인 상태는 목표 화면에 실제로 도착한 것을 본 뒤에만 저장한다
            if args.login_url and args.save_state:
                if any(m["to_login"] for m in report["widths"].values()):
                    print("주의: 목표 화면 대신 로그인 화면으로 열려 로그인 상태를 저장하지 않음")
                else:
                    Path(args.save_state).parent.mkdir(parents=True, exist_ok=True)
                    context.storage_state(path=args.save_state)
            tmp = report_path.with_suffix(".json.part")  # 다 쓴 뒤에만 report.json이 된다
            tmp.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, report_path)
        except Exception as e:
            first = scrub(str(e).splitlines()[0]) if str(e) else type(e).__name__
            print(f"요약: 종료 3, 실행 오류(report.json은 만들지 않음): {first}")
            if os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED"):
                print("샌드박스가 네트워크를 막았을 수 있다: 서버를 다시 띄우기 전에 승인을 받아(샌드박스 밖에서) 다시 실행한다")
            print("서버가 켜져 있는지, 주소·--ready 선택자·로그인 선택자·출력 폴더가 맞는지 확인한다")
            return 3
        finally:
            browser.close()
    problems = sum(min(m["page_overflow"], 1) + sum(m[k] for k in PROBLEM_KEYS if k != "page_overflow")
                   for m in report["widths"].values())  # 가로 넘침은 픽셀이 아니라 1건으로 센다
    code = 1 if problems else 0
    print(f"요약: 종료 {code}, 폭 {len(widths)}개, 문제 {problems}건, report: {out / 'report.json'}")
    for w, m in report["widths"].items():
        moved = (f", 로그인 화면으로 돌아감: {m['final_url']}(그 화면을 본 것이 아니다)" if m["to_login"]
                 else f", 다른 주소로 열림(정보): {m['final_url']}" if m["redirected"] else "")
        print(f"- 폭 {w}: 가로 넘침 {m['page_overflow']}px, 화면 밖 {m['offscreen']}, 잘림 {m['clipped']}, 말줄임 {m['ellipsis']}, "
              f"이름표 없는 입력 {m['unlabeled_inputs']}, 콘솔 오류 {m['console_errors']}, 실패 요청 {m['failed_requests']}{moved} → {m['png']}")
        if m.get("document_status") and 400 <= m["document_status"] < 500:
            print(f"    (페이지 응답 HTTP {m['document_status']}: 요구된 오류 화면인지 기대 상태와 견준다)")
        for key in ("offscreen", "clipped", "unlabeled", "console", "failed"):
            for ex in m.get(f"{key}_examples", []):
                print(f"    {key}: {ex}")
        for sc in m.get("scrollers", []):
            print(f"    가로 스크롤 영역(정보): {sc}")
    print("PNG는 이미지 보기 도구로 열어 본다. 찍었다고 본 것이 아니다.")
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # 드라이버 시작 실패처럼 예상 못 한 오류도 요약 줄과 종료 3으로 끝낸다
        first = scrub(str(e).splitlines()[0]) if str(e) else ""
        print(f"요약: 종료 3, 실행 오류: {type(e).__name__}: {first[:200]}")
        sys.exit(3)
