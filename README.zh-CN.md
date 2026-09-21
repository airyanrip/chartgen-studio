# 谱面生成工作室

[한국어](README.md) | [English](README.en.md) | [日本語](README.ja.md) | **简体中文**

根据音乐文件 (或 YouTube 链接) 自动生成节奏游戏谱面，并可直接在软件内试玩。
输出为 **osu!mania 的 `.osz`**，支持普通音符和**长条**。

## 功能

- **自动生成谱面**: 检测歌曲的 BPM 和节拍网格，把声音开始的位置对齐到网格并生成音符。持续较长的声音会变成长条。
- **键数**: 1-9 键 (默认 4 键)。可一次生成多个难度 (简单 / 普通 / 困难 / 极难)。
- **人声处理**: 用 demucs 分离人声 (歌词) 与伴奏，并可在三种模式中选择:
  - `ignore` 只根据伴奏生成谱面 (忽略人声)
  - `mix` 伴奏 + 人声一起
  - `only` 仅人声
  - 有人声的时间段会保存到 `<名称>.vocals.json`，之后可以对齐歌词 (例如 Whisper)。
- **YouTube 导入**: 使用 yt-dlp + ffmpeg 从链接下载音频 (可选 1080p 视频)。
- **试玩播放器**: 生成的谱面可以直接在窗口右侧游玩。支持 PERFECT / GREAT / GOOD / MISS 判定、FEVER 槽、圆环 / 矩形音符、波纹 / 爆裂打击特效，可调节音符速度、同步和判定宽度，支持按键设置、暂停 (ESC) 和重来 (R)。
- **多语言界面**: 한국어 / English / 日本語 / 简体中文。在窗口右上角选择后立即切换，下次启动时仍会保留。首次启动时跟随 Windows 的显示语言。(PERFECT / GREAT / GOOD / MISS 等游戏术语在所有语言中都保持英文。)
- 使用像素风字体: [Galmuri](https://github.com/quiple/galmuri) (韩语、英语、日语) 和 [Ark Pixel](https://github.com/TakWolf/ark-pixel-font) (中文)。两者均为 SIL OFL 1.1，许可证位于 `fonts/`。

## 运行要求

- Windows 10/11
- Python 3.11 (推荐 [uv](https://docs.astral.sh/uv/))
- 推荐 NVIDIA GPU (人声分离会快很多；没有 GPU 时也可使用 CPU 版 PyTorch，只是较慢)

## 安装

```powershell
git clone <本仓库地址> chartgen
cd chartgen

uv venv --python 3.11 .venv

# 1) 先安装 PyTorch。(GPU: CUDA 12.6 版本 / 仅 CPU 时不加 --index-url，直接安装 `torch`)
uv pip install --python .venv\Scripts\python.exe torch --index-url https://download.pytorch.org/whl/cu126

# 2) 其余依赖包
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

把三个可执行文件放进 `tools\` 文件夹。(体积较大，因此没有包含在仓库中)

```powershell
mkdir tools
# yt-dlp
curl.exe -L -o tools\yt-dlp.exe https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe
# deno (yt-dlp 解析 YouTube 时使用的 JavaScript 运行时)
curl.exe -L -o deno.zip https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip
Expand-Archive deno.zip tools ; del deno.zip
# ffmpeg: 从 https://www.gyan.dev/ffmpeg/builds/ 下载，并把 ffmpeg.exe 复制到 tools\
#         (或执行 `winget install Gyan.FFmpeg`，再复制已安装的 ffmpeg.exe)
```

首次分离人声时，demucs 模型 (约 80MB) 会自动下载到 `models\`。

## 运行

图形界面:

```powershell
.venv\Scripts\pythonw.exe gui.py
```

也可以打包成 exe。这个 exe 只是一个小型启动器 (约 8MB)，作用是代为执行上面的命令，因此必须放在项目文件夹内。

```powershell
uv pip install --python .venv\Scripts\python.exe pyinstaller
.venv\Scripts\pyinstaller.exe --onefile --noconsole --name ChartGen launcher.py   # dist\ChartGen.exe
```

命令行:

```powershell
run.bat "song.mp3" --keys 4 --difficulty normal,hard --vocals mix
```

| 选项 | 说明 | 默认值 |
|---|---|---|
| `--keys N` | 轨道数 (1-9) | 4 |
| `--difficulty` | `easy,normal,hard,insane` (可用逗号指定多个) | normal |
| `--vocals` | `ignore` / `mix` / `only` | ignore |
| `--no-long-notes` | 关闭长条 | |
| `--max-ln-ratio` | 长条的最大占比 | 0.35 |
| `--sustain` | 长条判定标准 (越低长条越多) | 0.6 |
| `--ln-min-beats` / `--ln-max-beats` | 长条的最短 / 最长长度 (拍) | 1 / 4 |
| `--bpm` | 手动指定 BPM | 自动检测 |
| `--seed` | 相同的值会得到相同的谱面 | 0 |
| `--title` `--artist` `--creator` | 元数据 | |
| `-o` | 输出的 `.osz` 路径 | 音乐文件旁边 |

生成的 `.osz` 在 osu! 中双击即可打开。

## 项目结构

| 文件 | 作用 |
|---|---|
| `chartgen.py` | 谱面生成 (分析 → 节拍网格 → 起音点 / 长条 → 轨道分配 → `.osz`) |
| `game.py` | 试玩播放器。计分逻辑 (`Session`) 与界面和音频相互独立 |
| `gui.py` | 主窗口 (歌曲 / 谱面 / 曲库 标签页 + 播放器) |
| `theme.py` | 颜色、按语言加载字体、ttk 样式 |
| `i18n.py` | 四种语言的翻译表 (`t("键")`)。修改措辞或添加语言都在这里进行 |
| `launcher.py` | exe 启动器 |
| `tests/test_session.py` | 计分逻辑测试 (`.venv\Scripts\python.exe tests\test_session.py`) |
| `tests/test_i18n.py` | 翻译测试: 缺失的键、`{占位符}` 是否一致、字体中缺少的字符 (字符检查需要 `pip install fonttools`) |

要修改翻译，只需编辑 `i18n.py` 中对应的那一行。新增文案时必须填写四种语言，否则 `tests/test_i18n.py` 会失败。

## 注意事项

- 整首歌按**单一 BPM** 处理。速度会变化的歌曲，后半段可能出现偏差。
- 试玩播放器基于 Tk，按键时间不够精确。它适合用来检查谱面；如果觉得声音偏晚，请调整同步 (ms)。当输入法处于韩语 / 日语 / 中文输入状态时，按键可能会被识别为其他值，请在英文输入状态下游玩。
- 相同的歌曲、相同的选项和相同的 `--seed`，即使使用了人声分离，也会得到相同的谱面。(demucs 以 `--shifts=0` 运行。)
- 下载 YouTube 视频可能涉及版权问题，也可能违反 YouTube 的服务条款。请仅用于个人练习，分享谱面前请确认原曲的权利。

## 第三方组件

demucs (MIT)、librosa (ISC)、PyTorch (BSD)、pygame (LGPL)、yt-dlp (Unlicense)、FFmpeg (视构建而定，LGPL/GPL)、Deno (MIT)、Galmuri 字体 (SIL OFL 1.1)、Ark Pixel 字体 (SIL OFL 1.1)。
