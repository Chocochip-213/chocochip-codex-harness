#!/usr/bin/env python3
"""환경 점검: 구현 선택을 바꾸는 사실만 짧게 보여 준다.

사용: python3 env_check.py
- 파이썬 버전, glibc, pip, PyPI 접속(이 프로세스 기준), sqlite·시간대·날짜 파싱,
  이미 깔린 주요 패키지, 쓸 수 있는 포트, git 상태.
- 표준 라이브러리만 쓰고, 아무것도 설치하거나 고치지 않는다.
"""
import errno
import importlib.metadata as md
import importlib.util
import os
import platform
import shutil
import socket
import sqlite3
import subprocess
import sys

import signal
if hasattr(signal, "SIGPIPE"):  # 출력을 head 등으로 자를 때 오류 없이 끝낸다
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

PACKAGES = ["numpy", "pandas", "scipy", "flask", "fastapi", "uvicorn", "pytest", "rapidfuzz",
            "duckdb", "openpyxl", "matplotlib", "pulp", "ortools", "sklearn", "dateutil", "openai"]
DIST = {"sklearn": "scikit-learn", "dateutil": "python-dateutil"}
PORTS = [8000, 8080, 3000, 5000]


def run(cmd, timeout=10):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or p.stderr).strip().splitlines()[:1]
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, [type(e).__name__]


def line(label, value):
    print(f"- {label}: {value}")


def main():
    print("== 환경")
    sandbox = os.environ.get("CODEX_SANDBOX") or os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED")
    if sandbox:
        print("- 주의: Codex 샌드박스 안에서 실행 중이다. 네트워크·포트 결과는 실제와 다를 수 있다"
              "(shell 탭에서 다시 실행해 확인).")
    line("파이썬", f"{platform.python_version()} ({sys.executable})")
    libc = " ".join(x for x in platform.libc_ver() if x) or "알 수 없음"
    line("OS·libc", f"{platform.system()} {platform.machine()}, {libc}")

    code, out = run([sys.executable, "-m", "pip", "--version"])
    line("pip", out[0] if code == 0 and out else "없음")
    try:
        socket.create_connection(("pypi.org", 443), timeout=3).close()
        net = "열림"
    except OSError as e:
        net = f"막힘({type(e).__name__}) — 이 프로세스 기준이다. Codex 샌드박스라면 승인 뒤에는 될 수 있다"
    line("PyPI 접속", net)

    line("sqlite", sqlite3.sqlite_version)
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo("Asia/Seoul")
        tz = "Asia/Seoul 있음"
    except Exception as e:  # zoneinfo 없음, tz 데이터 없음
        tz = f"Asia/Seoul 없음({type(e).__name__}) — 고정 +09:00이나 tzdata 필요"
    line("시간대", tz)
    from datetime import datetime
    try:
        datetime.fromisoformat("2026-10-31T01:00:00Z")
        iso = "fromisoformat이 'Z'를 읽음"
    except ValueError:
        iso = "fromisoformat이 'Z'를 못 읽음 — 'Z'를 '+00:00'으로 바꿔 읽기"
    line("날짜 파싱", iso)

    have, missing = [], []
    for name in PACKAGES:
        if importlib.util.find_spec(name) is None:
            missing.append(name)
            continue
        try:
            have.append(f"{name} {md.version(DIST.get(name, name))}")
        except md.PackageNotFoundError:
            have.append(name)
    line("이미 있는 패키지", ", ".join(have) or "없음")
    line("없는 패키지", ", ".join(missing) or "없음")

    free = []
    for port in PORTS:
        s = None
        try:
            s = socket.socket()
            s.bind(("0.0.0.0", port))
            free.append(f"{port} 빈 포트")
        except OSError as e:
            if e.errno == errno.EADDRINUSE:
                free.append(f"{port} 사용 중")
            else:
                free.append(f"{port} 확인 불가({type(e).__name__})")
        finally:
            if s is not None:
                s.close()
    line("포트(이 프로세스 기준)", ", ".join(free))

    tools = [t for t in ("git", "curl", "node", "npm", "codex") if shutil.which(t)]
    line("명령", ", ".join(tools) or "없음")
    code, out = run(["git", "rev-parse", "--show-toplevel"])
    if code == 0 and out:
        top = out[0]
        here = os.path.realpath(os.getcwd())
        line("git 저장소 맨 위", top + ("" if os.path.realpath(top) == here else f" (지금 폴더 {here}와 다름)"))
        code, out = run(["git", "config", "user.name"])
        line("git 사용자 이름", out[0] if code == 0 and out else "없음 — 커밋 전에 설정 필요")
        code, out = run(["git", "config", "user.email"])
        line("git 이메일", "설정됨" if code == 0 and out else "없음 — 커밋 전에 설정 필요")
    else:
        line("git", "저장소 아님")
    return 0


if __name__ == "__main__":
    sys.exit(main())
