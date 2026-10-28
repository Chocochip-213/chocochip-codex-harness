# 문제 유형별로 쓸 것 (표준 라이브러리 먼저)

원칙
- 표준 라이브러리로 되면 그걸 쓴다. 패키지는 `env_check.py`에 이미 있다고 나왔거나 pip가 될 때만, 넣기 전에 사용자에게 묻는다.
- 결과를 사람이 설명할 수 있어야 한다. README·담당자가 요구하지 않으면 블랙박스(랜덤포레스트 중요도, SHAP 등)는 쓰지 않는다.
- 작업 환경의 버전은 `env_check.py`로 다시 본다.

| 유형 | 표준 라이브러리로 | 패키지(있을 때) | 함정 |
|---|---|---|---|
| 웹 서버·검토 화면 | `http.server`(서버 파일 하나) | flask | 0.0.0.0, 화면의 경로는 상대 경로 |
| 섞인 날짜·시간대 | `datetime.fromisoformat` → 안 되면 `strptime` 형식 목록, `zoneinfo` | python-dateutil(실패한 행에만) | 3.10은 'Z'를 못 읽어 '+00:00'으로 바꿔 읽는다. 시간대 없는 값은 어느 시간대인지부터 확인하고, 정한 뒤 한곳에서 바꾼다. 어떤 형식으로 읽혔는지 열로 남기고 실패 행은 따로 |
| 표기 흔들림·이름 매칭 | NFKC + `casefold()` + 영숫자만 남긴 키 → `difflib.get_close_matches(cutoff=0.8)` | rapidfuzz | rapidfuzz는 `processor=utils.default_process`를 줘야 대소문자를 무시한다. 자동 확정 말고 '사람 확인' 목록으로 |
| 중복·연쇄 이벤트 묶기 | 키·시각으로 정렬 → `itertools.groupby` + 간격 기준, 시작·종료는 키별 dict로 짝 맞춤, `sqlite3`의 `LAG()` | duckdb(ASOF JOIN) | 짝 없는 시작·종료는 따로 표로. duckdb는 `fetchall()`로 받는다(`.df()`는 pandas 필요) |
| 조인 | dict로 합치기 | — | 합치기 전에 `join_check.py`로 키 중복(행 불어남)과 짝 없는 키(조용히 빠짐)를 본다 |
| 그룹 비교(비율·평균) | n·평균·비율·차이 표 먼저, 두 비율 z검정은 `statistics.NormalDist`, 평균 차이는 순열검정 | scipy.stats | 표본 수를 같이 보인다 |
| 기여 요인 찾기 | 요인 값별 (그 집단 불량률 − 전체 불량률) × 비중으로 정렬 | — | 근거 행 수를 같이 보인다 |
| 이상치·추세 변화 | 중앙값·MAD 로버스트 z(3.5 초과), `statistics.quantiles` IQR, CUSUM | ruptures | 걸린 규칙 이름을 열로 남긴다 |
| 배정·일정 | 마감·우선순위 `heapq` 그리디, 작은 경우 `itertools.permutations`로 최적과 비교 | `pulp==3.3.2`(반드시 버전 고정), scipy `optimize.milp` | PuLP 4.x는 문법이 다르고 numpy가 없으면 import가 실패한다 |
| 재고·안전재고 | `statistics.NormalDist().inv_cdf(서비스수준)` | — | 일수요 표준편차 × √리드타임. 과제 기준이 따로 있으면 그것을 따른다 |
| 회귀 테스트(기존 코드 고치기) | `unittest` + 지금 출력을 골든 JSON으로 고정 + `difflib` | pytest | 고치기 전에 현재 출력부터 고정한다 |
| 표·차트 | SVG 문자열, 또는 `.harness/vendor/chart.umd.min.js`를 static/에 복사 | — | 외부 CDN에 기대지 않는다(미리보기에서 막힐 수 있음) |
| 한글 CSV 인코딩 | `utf-8-sig` → 안 되면 `cp949` | — | 어느 쪽으로 읽혔는지 출력한다 |
| 엑셀 | `zipfile` + `xml.etree` | openpyxl(`read_only=True, data_only=True`) | 병합 셀·빈 헤더를 먼저 확인 |
| SQL 집계 | `sqlite3`(윈도 함수는 3.25 이상) | duckdb | 쓴 SQL은 파일로 남긴다 |

넣지 않은 것과 이유
- matplotlib 차트: 기본 글꼴에 한글이 없어 깨진다. 브라우저 차트를 쓴다.
- Streamlit, Datasette: 의존성이 많고 미리보기 프록시를 통과하는지 확인되지 않았다.
- statsmodels, scikit-learn, OR-Tools: 설치가 크고(수십 MB), 180분 안에 결과를 설명하기 어렵다. 표준 대안이 있다.
- 오프라인 wheel 묶음: 작업 환경의 파이썬·glibc 버전을 모른다. 작업 환경에서 pip가 막혀 있으면 그때 다시 정한다.
