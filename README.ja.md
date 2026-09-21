# 譜面生成スタジオ

[한국어](README.md) | [English](README.en.md) | **日本語** | [简体中文](README.zh-CN.md)

音楽ファイル (または YouTube の URL) からリズムゲームの譜面を自動で作り、アプリ内ですぐに試しプレイできるツールです。
出力は **osu!mania の `.osz`** で、通常ノーツと**ロングノート**に対応しています。

## 機能

- **自動譜面生成**: 曲の BPM と拍のグリッドを見つけ、音が鳴り始める位置をグリッドに合わせてノーツにします。音が長く続く部分はロングノートになります。
- **キー数**: 1〜9キー (初期値は4キー)。難易度 (イージー / ノーマル / ハード / インセイン) を一度に複数作れます。
- **ボーカルの扱い**: ボーカル (歌詞) と伴奏を demucs で分離し、次の3つから選べます。
  - `ignore` 伴奏だけを見て譜面を作る (ボーカルは無視)
  - `mix` 伴奏 + ボーカルの両方
  - `only` ボーカルのみ
  - ボーカルが入っている区間は `<名前>.vocals.json` に保存されるので、後から歌詞 (例: Whisper) を合わせられます。
- **YouTube 取得**: yt-dlp + ffmpeg で URL から音声 (任意で 1080p の動画) をダウンロードします。
- **テストプレイヤー**: 作った譜面をウィンドウ右側でそのままプレイできます。PERFECT / GREAT / GOOD / MISS 判定、FEVER ゲージ、リング / 長方形ノーツ、波紋 / バーストのヒットエフェクト、ノーツ速度・同期・判定幅の調整、キー設定、一時停止 (ESC)・やり直し (R) に対応しています。
- **多言語 UI**: 한국어 / English / 日本語 / 简体中文。ウィンドウ右上で選ぶとすぐに切り替わり、次回の起動でも保持されます。初回は Windows の表示言語に従います。(PERFECT / GREAT / GOOD / MISS などのゲーム用語は、どの言語でも英語のままです。)
- ドット絵風フォントを使用しています: [Galmuri](https://github.com/quiple/galmuri) (韓国語・英語・日本語) と [Ark Pixel](https://github.com/TakWolf/ark-pixel-font) (中国語)。どちらも SIL OFL 1.1 で、ライセンスは `fonts/` にあります。

## 動作環境

- Windows 10/11
- Python 3.11 ([uv](https://docs.astral.sh/uv/) 推奨)
- NVIDIA GPU 推奨 (ボーカル分離が高速になります。GPU がなくても CPU 版 PyTorch で動作しますが遅くなります)

## インストール

```powershell
git clone <このリポジトリの URL> chartgen
cd chartgen

uv venv --python 3.11 .venv

# 1) 先に PyTorch をインストールします。(GPU: CUDA 12.6 ビルド / CPU のみの場合は --index-url なしの `torch`)
uv pip install --python .venv\Scripts\python.exe torch --index-url https://download.pytorch.org/whl/cu126

# 2) 残りのパッケージ
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

`tools\` フォルダに実行ファイルを3つ置きます。(サイズが大きいためリポジトリには含めていません)

```powershell
mkdir tools
# yt-dlp
curl.exe -L -o tools\yt-dlp.exe https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe
# deno (yt-dlp が YouTube の解析に使う JavaScript ランタイム)
curl.exe -L -o deno.zip https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip
Expand-Archive deno.zip tools ; del deno.zip
# ffmpeg: https://www.gyan.dev/ffmpeg/builds/ からダウンロードし、ffmpeg.exe を tools\ にコピー
#         (または `winget install Gyan.FFmpeg` の後、インストールされた ffmpeg.exe をコピー)
```

初めてボーカルを分離するとき、demucs のモデル (約 80MB) が `models\` に自動でダウンロードされます。

## 実行

GUI:

```powershell
.venv\Scripts\pythonw.exe gui.py
```

exe にまとめることもできます。この exe は上のコマンドを代わりに実行する小さなランチャー (約 8MB) なので、プロジェクトフォルダ内に置く必要があります。

```powershell
uv pip install --python .venv\Scripts\python.exe pyinstaller
.venv\Scripts\pyinstaller.exe --onefile --noconsole --name ChartGen launcher.py   # dist\ChartGen.exe
```

コマンドライン:

```powershell
run.bat "song.mp3" --keys 4 --difficulty normal,hard --vocals mix
```

| オプション | 説明 | 初期値 |
|---|---|---|
| `--keys N` | レーン数 (1〜9) | 4 |
| `--difficulty` | `easy,normal,hard,insane` (カンマ区切りで複数指定可) | normal |
| `--vocals` | `ignore` / `mix` / `only` | ignore |
| `--no-long-notes` | ロングノートを使わない | |
| `--max-ln-ratio` | ロングノートの最大割合 | 0.35 |
| `--sustain` | ロングノートの判定基準 (低いほどロングノートが増える) | 0.6 |
| `--ln-min-beats` / `--ln-max-beats` | ロングノートの最小 / 最大の長さ (拍) | 1 / 4 |
| `--bpm` | BPM を手動で指定 | 自動検出 |
| `--seed` | 同じ値なら同じ譜面になる | 0 |
| `--title` `--artist` `--creator` | メタデータ | |
| `-o` | 出力する `.osz` のパス | 音楽ファイルの隣 |

できあがった `.osz` は osu! でダブルクリックするとそのまま開けます。

## 構成

| ファイル | 役割 |
|---|---|
| `chartgen.py` | 譜面生成 (解析 → 拍グリッド → オンセット / ロングノート → レーン配置 → `.osz`) |
| `game.py` | テストプレイヤー。採点ロジック (`Session`) は GUI や音声から分離されています |
| `gui.py` | メインウィンドウ (曲 / 譜面 / ライブラリのタブ + プレイヤー) |
| `theme.py` | 色、言語ごとのフォント読み込み、ttk スタイル |
| `i18n.py` | 4言語の翻訳テーブル (`t("キー")`)。文言の修正や言語の追加はここで行います |
| `launcher.py` | exe ランチャー |
| `tests/test_session.py` | 採点ロジックのテスト (`.venv\Scripts\python.exe tests\test_session.py`) |
| `tests/test_i18n.py` | 翻訳のテスト: キーの欠落、`{プレースホルダー}` の一致、フォントにない文字の検査 (文字検査には `pip install fonttools` が必要) |

翻訳を直すには `i18n.py` の該当行だけを編集します。新しい文言を追加するときは4言語すべてを埋めないと `tests/test_i18n.py` が失敗します。

## 注意事項

- 曲全体を**単一の BPM** として扱います。テンポが変わる曲は、後半でずれることがあります。
- テストプレイヤーは Tk ベースのため、キー入力の時刻は精密ではありません。譜面の確認用として使い、音が遅れて聞こえる場合は同期 (ms) を調整してください。IME が韓国語・日本語・中国語の入力モードだとキーが別の値で届くことがあるので、英数入力モードでプレイしてください。
- 同じ曲・同じオプション・同じ `--seed` なら、ボーカル分離を使っても同じ譜面になります。(demucs は `--shifts=0` で実行します。)
- YouTube 動画のダウンロードは、著作権や YouTube の利用規約に抵触する場合があります。個人の練習用にとどめ、作った譜面を配布するときは元の楽曲の権利を確認してください。

## サードパーティ

demucs (MIT)、librosa (ISC)、PyTorch (BSD)、pygame (LGPL)、yt-dlp (Unlicense)、FFmpeg (ビルドにより LGPL/GPL)、Deno (MIT)、Galmuri フォント (SIL OFL 1.1)、Ark Pixel フォント (SIL OFL 1.1)。
