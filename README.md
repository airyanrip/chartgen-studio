# 채보 생성 스튜디오

**한국어** | [English](README.en.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

음악 파일(또는 유튜브 URL)에서 리듬게임 채보를 자동으로 만들고, 프로그램 안에서 바로 쳐 볼 수 있는 도구입니다.
출력은 **osu!mania `.osz`** 이고 일반 노트와 **롱노트**를 지원합니다.

## 기능

- **자동 채보**: 곡의 BPM과 박자 격자를 찾고, 소리가 시작되는 지점을 격자에 맞춰 노트로 만듭니다. 소리가 길게 이어지는 곳은 롱노트가 됩니다.
- **키 개수**: 1~9키 (기본 4키). 난이도 4단계(쉬움 / 보통 / 어려움 / 매우 어려움)를 한 번에 만들 수 있습니다.
- **보컬 처리**: 보컬(가사)과 반주를 분리(demucs)해서 세 가지 중에서 고릅니다.
  - `ignore` 반주만 보고 채보 (보컬 무시)
  - `mix` 반주 + 보컬 함께
  - `only` 보컬만
  - 보컬이 나오는 구간은 `<이름>.vocals.json` 으로 따로 저장되어, 가사(예: Whisper)를 나중에 맞춰 붙일 수 있습니다.
- **유튜브 가져오기**: yt-dlp + ffmpeg 로 URL에서 오디오(선택: 1080p 영상)를 받습니다.
- **테스트 플레이어**: 만든 채보를 창 오른쪽에서 바로 플레이합니다. PERFECT / GREAT / GOOD / MISS 판정, FEVER 게이지, 링/직사각형 노트, 물결/터지는 이펙트, 노트 속도·싱크·판정 폭 조절, 키 설정, 일시정지(ESC)·다시 시작(R)을 지원합니다.
- **다국어 UI**: 한국어 / English / 日本語 / 简体中文. 창 오른쪽 위에서 고르면 바로 바뀌고 다음 실행에도 유지됩니다. 처음에는 윈도우 표시 언어를 따릅니다. (판정 이름 PERFECT / GREAT / GOOD / MISS 등 게임 용어는 모든 언어에서 영어 그대로입니다)
- 도트풍 폰트를 사용합니다: [갈무리(Galmuri)](https://github.com/quiple/galmuri) (한국어·영어·일본어), [Ark Pixel](https://github.com/TakWolf/ark-pixel-font) (중국어). 둘 다 SIL OFL 1.1 이고 라이선스는 `fonts/` 에 있습니다.

## 요구 사항

- Windows 10/11
- Python 3.11 ([uv](https://docs.astral.sh/uv/) 권장)
- NVIDIA GPU 권장 (보컬 분리가 빠릅니다. 없으면 CPU 버전 PyTorch로도 동작하지만 느립니다)

## 설치

```powershell
git clone <이 저장소 주소> chartgen
cd chartgen

uv venv --python 3.11 .venv

# 1) PyTorch를 먼저 설치합니다. (GPU: CUDA 12.6 빌드 / CPU만 쓸 때는 --index-url 없이 `torch`)
uv pip install --python .venv\Scripts\python.exe torch --index-url https://download.pytorch.org/whl/cu126

# 2) 나머지 패키지
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

`tools\` 폴더에 실행 파일 3개를 넣습니다. (용량이 커서 저장소에는 포함하지 않았습니다)

```powershell
mkdir tools
# yt-dlp
curl.exe -L -o tools\yt-dlp.exe https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe
# deno (yt-dlp가 유튜브 분석에 사용하는 JavaScript 런타임)
curl.exe -L -o deno.zip https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip
Expand-Archive deno.zip tools ; del deno.zip
# ffmpeg: https://www.gyan.dev/ffmpeg/builds/ 에서 받아 ffmpeg.exe 를 tools\ 에 복사
#         (또는 `winget install Gyan.FFmpeg` 후 설치된 ffmpeg.exe 를 복사)
```

첫 보컬 분리 때 demucs 모델(약 80MB)이 `models\` 에 자동으로 내려받아집니다.

## 실행

GUI:

```powershell
.venv\Scripts\pythonw.exe gui.py
```

원하면 실행 파일로 묶을 수 있습니다. 이 exe는 위 명령을 대신 실행해 주는 작은 런처(약 8MB)이며, 프로젝트 폴더 안에 두어야 합니다.

```powershell
uv pip install --python .venv\Scripts\python.exe pyinstaller
.venv\Scripts\pyinstaller.exe --onefile --noconsole --name ChartGen launcher.py   # dist\ChartGen.exe
```

명령줄:

```powershell
run.bat "song.mp3" --keys 4 --difficulty normal,hard --vocals mix
```

| 옵션 | 설명 | 기본값 |
|---|---|---|
| `--keys N` | 레인 수 (1~9) | 4 |
| `--difficulty` | `easy,normal,hard,insane` (쉼표로 여러 개) | normal |
| `--vocals` | `ignore` / `mix` / `only` | ignore |
| `--no-long-notes` | 롱노트 끄기 | |
| `--max-ln-ratio` | 롱노트 최대 비율 | 0.35 |
| `--sustain` | 롱노트 판정 기준 (낮을수록 롱노트가 많아짐) | 0.6 |
| `--ln-min-beats` / `--ln-max-beats` | 롱노트 최소/최대 길이(박) | 1 / 4 |
| `--bpm` | BPM을 직접 지정 | 자동 감지 |
| `--seed` | 같은 값이면 같은 채보 | 0 |
| `--title` `--artist` `--creator` | 메타데이터 | |
| `-o` | 출력 `.osz` 경로 | 음악 옆 |

결과 `.osz`는 osu!에서 더블클릭하면 바로 열립니다.

## 구성

| 파일 | 역할 |
|---|---|
| `chartgen.py` | 채보 생성 (분석 → 박자 격자 → 온셋/롱노트 → 레인 배치 → `.osz`) |
| `game.py` | 테스트 플레이어. 채점 로직(`Session`)은 GUI/오디오와 분리되어 있습니다 |
| `gui.py` | 메인 창 (곡/채보/라이브러리 탭 + 플레이어) |
| `theme.py` | 색상, 언어별 폰트 로딩, ttk 스타일 |
| `i18n.py` | 4개 언어 번역 테이블 (`t("키")`). 문구를 고치거나 언어를 추가하는 곳입니다 |
| `launcher.py` | exe 런처 |
| `tests/test_session.py` | 채점 로직 테스트 (`.venv\Scripts\python.exe tests\test_session.py`) |
| `tests/test_i18n.py` | 번역 테스트: 키 누락, `{자리표시자}` 일치, 폰트에 없는 글자 검사 (글자 검사는 `pip install fonttools` 필요) |

번역을 고치려면 `i18n.py` 의 해당 줄만 수정하면 됩니다. 새 문구를 추가하면 4개 언어를 모두 채워야 `tests/test_i18n.py` 가 통과합니다.

## 알아둘 점

- 곡 전체를 **하나의 BPM** 으로 처리합니다. 템포가 바뀌는 곡은 뒤쪽이 어긋날 수 있습니다.
- 테스트 플레이어는 Tk 기반이라 키 입력 시각이 정밀하지 않습니다. 채보 확인용이며, 소리가 늦게 들리면 싱크(ms)를 조절하세요. 한글 입력 상태에서는 키가 다르게 들어올 수 있으니 영문 상태에서 플레이하세요.
- 같은 곡, 같은 옵션, 같은 `--seed` 이면 보컬 분리를 쓴 경우에도 같은 채보가 나옵니다. (demucs는 `--shifts=0` 으로 실행)
- 유튜브 영상을 내려받는 것은 저작권과 유튜브 약관에 걸릴 수 있습니다. 개인 연습용으로만 사용하고, 만든 채보를 배포할 때는 원곡의 권리를 확인하세요.

## 서드파티

demucs (MIT), librosa (ISC), PyTorch (BSD), pygame (LGPL), yt-dlp (Unlicense), FFmpeg (LGPL/GPL 빌드에 따름), Deno (MIT), Galmuri 폰트 (SIL OFL 1.1), Ark Pixel 폰트 (SIL OFL 1.1).
