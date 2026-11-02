# ui_check 동봉 파일

`tools/ui_check.py`가 리눅스에서 쓴다. 한글 글꼴이 없으면 `fonts/`를 사용자 글꼴 폴더에 두고, 브라우저 시스템 라이브러리를 그 컴퓨터에 맞게 받지 못하면 `libs-ubuntu22.04-amd64/`를 예비로 쓴다. 모두 우분투 22.04(jammy) amd64 공식 패키지에서 고치지 않고 꺼낸 파일이다.

| 폴더 | 원래 패키지(소스 패키지) | 버전 | 라이선스 | 고지·소스 |
|---|---|---|---|---|
| `fonts/NanumGothic.ttf`, `NanumGothicBold.ttf` | fonts-nanum | 20200506-1 | SIL OFL 1.1 | `licenses/fonts-nanum.copyright`(저작권·예약 이름·OFL 전문) |
| `libs-ubuntu22.04-amd64/libnss3.so` 외 NSS(`nss/` 포함) | libnss3(nss) | 2:3.98-0ubuntu0.22.04.5 | MPL 2.0 | `licenses/libnss3.copyright`, `licenses/MPL-2.0.txt`. 소스: https://launchpad.net/ubuntu/+source/nss/2:3.98-0ubuntu0.22.04.5 |
| `libs-ubuntu22.04-amd64/libnspr4.so`, `libplc4.so`, `libplds4.so` | libnspr4(nspr) | 2:4.35-0ubuntu0.22.04.1 | MPL 2.0 | `licenses/libnspr4.copyright`, `licenses/MPL-2.0.txt`. 소스: https://launchpad.net/ubuntu/+source/nspr/2:4.35-0ubuntu0.22.04.1 |
| `libs-ubuntu22.04-amd64/libasound.so.2` | libasound2(alsa-lib) | 1.2.6.1-1ubuntu1.2 | LGPL 2.1 | `licenses/libasound2.copyright`, `licenses/LGPL-2.1.txt`. 대응 소스 전부(원본·우분투 패치·빌드 설명)를 `source/alsa-lib/`에 같이 둔다(같은 파일을 https://launchpad.net/ubuntu/+source/alsa-lib/1.2.6.1-1ubuntu1.2 에서도 받을 수 있다) |

- `source/alsa-lib/`의 SHA-256: `alsa-lib_1.2.6.1.orig.tar.bz2` ad582993d52cdb5fb159a0beab60a6ac57eab0cc1bdf85dc4db6d6197f02333f, `alsa-lib_1.2.6.1-1ubuntu1.2.debian.tar.xz` fd30152719525f094a951c63811bfcb7410f5d6b8d63987e9f71a95deb2a95e7(`.dsc`의 값과 같다).
- 라이브러리 이름은 패키지의 링크 이름을 실제 파일로 바꿔 둔 것이다(`libasound.so.2`는 `libasound.so.2.0.0`과 같은 파일).
