"""UI strings in Korean / English / Japanese / Simplified Chinese.

t("key", name=value) returns the text in the current language ({name} placeholders are filled in).
Game terms (PERFECT, GREAT, GOOD, MISS, FEVER, COMBO, BPM, MAX COMBO) stay in English in every language.
"""
import ctypes

LANGS = {"ko": "한국어", "en": "English", "ja": "日本語", "zh": "简体中文"}
DEFAULT = "en"

# key: (ko, en, ja, zh)
_T = {
    # ---- window / header
    "app.title": ("채보 생성 스튜디오", "Chart Generation Studio", "譜面生成スタジオ", "谱面生成工作室"),
    "app.subtitle": ("자동 채보 생성 · 테스트 플레이", "Auto chart generation · test play",
                     "自動譜面生成 · テストプレイ", "自动谱面生成 · 试玩"),
    "tab.song": ("곡", "Song", "曲", "歌曲"),
    "tab.chart": ("채보", "Chart", "譜面", "谱面"),
    "tab.library": ("라이브러리", "Library", "ライブラリ", "曲库"),
    "btn.generate": ("채보 생성", "Generate chart", "譜面を生成", "生成谱面"),
    "btn.stop": ("중지", "Stop", "停止", "停止"),
    "btn.open_folder": ("결과 폴더 열기", "Open folder", "フォルダを開く", "打开文件夹"),
    "status.idle": ("대기 중", "Idle", "待機中", "待机中"),

    # ---- song tab
    "box.audio": ("음악 파일", "Music file", "音楽ファイル", "音乐文件"),
    "lbl.input": ("입력", "Input", "入力", "输入"),
    "btn.browse": ("찾아보기", "Browse", "参照", "浏览"),
    "lbl.save": ("저장", "Save to", "保存先", "保存到"),
    "btn.pick": ("지정", "Set", "指定", "指定"),
    "hint.default_out": ("비워 두면 {path} 에 저장", "Leave empty to save to {path}",
                         "空欄の場合は {path} に保存", "留空则保存到 {path}"),
    "box.youtube": ("유튜브에서 가져오기", "Import from YouTube", "YouTubeから取得", "从 YouTube 导入"),
    "lbl.url": ("URL", "URL", "URL", "URL"),
    "btn.fetch": ("가져오기", "Fetch", "取得", "获取"),
    "chk.save_video": ("영상(mp4)도 함께 저장", "Also save the video (mp4)", "動画(mp4)も保存", "同时保存视频(mp4)"),
    "hint.dl_dir": ("받은 파일: {path}", "Downloads: {path}", "保存先: {path}", "下载位置: {path}"),
    "box.info": ("곡 정보", "Song info", "曲情報", "歌曲信息"),
    "lbl.title": ("제목", "Title", "タイトル", "标题"),
    "lbl.artist": ("아티스트", "Artist", "アーティスト", "艺术家"),
    "lbl.creator": ("제작자", "Creator", "制作者", "制作者"),

    # ---- chart tab
    "box.chartset": ("채보 설정", "Chart settings", "譜面設定", "谱面设置"),
    "lbl.keys": ("키 개수", "Keys", "キー数", "键数"),
    "hint.keys": ("4키, 6키 등", "4K, 6K, ...", "4K、6K など", "4K、6K 等"),
    "lbl.difficulty": ("난이도", "Difficulty", "難易度", "难度"),
    "diff.easy": ("쉬움", "Easy", "イージー", "简单"),
    "diff.normal": ("보통", "Normal", "ノーマル", "普通"),
    "diff.hard": ("어려움", "Hard", "ハード", "困难"),
    "diff.insane": ("매우 어려움", "Insane", "インセイン", "极难"),
    "lbl.vocals": ("보컬 처리", "Vocals", "ボーカル", "人声处理"),
    "vocal.ignore": ("반주만 (보컬 무시)", "Backing only (ignore vocals)", "伴奏のみ (ボーカルを無視)", "仅伴奏 (忽略人声)"),
    "vocal.mix": ("반주 + 보컬 함께", "Backing + vocals", "伴奏 + ボーカル", "伴奏 + 人声"),
    "vocal.only": ("보컬만", "Vocals only", "ボーカルのみ", "仅人声"),
    "box.ln": ("롱노트", "Long notes", "ロングノート", "长条"),
    "chk.ln": ("롱노트 사용", "Use long notes", "ロングノートを使う", "使用长条"),
    "lbl.ln_ratio": ("비율 상한", "Max share", "割合の上限", "比例上限"),
    "lbl.ln_sus": ("판정 기준", "Threshold", "判定基準", "判定标准"),
    "hint.ln": ("판정 기준을 낮추면 롱노트가 더 많이 생깁니다.", "A lower threshold creates more long notes.",
                "判定基準を下げるとロングノートが増えます。", "降低判定标准会产生更多长条。"),
    "box.adv": ("고급", "Advanced", "詳細", "高级"),
    "chk.auto_bpm": ("BPM 자동 감지", "Detect BPM automatically", "BPMを自動検出", "自动检测 BPM"),
    "lbl.bpm": ("BPM", "BPM", "BPM", "BPM"),
    "lbl.seed": ("시드", "Seed", "シード", "种子"),

    # ---- library tab
    "lib.hint": ("만든 채보 (더블클릭하면 오른쪽 플레이어에 불러옵니다)",
                 "Your charts (double-click to load into the player on the right)",
                 "作成した譜面 (ダブルクリックで右のプレイヤーに読み込み)",
                 "已生成的谱面 (双击载入右侧播放器)"),
    "btn.load": ("불러오기", "Load", "読み込み", "载入"),
    "btn.open_osz": (".osz 열기...", "Open .osz...", ".osz を開く...", "打开 .osz..."),
    "btn.refresh": ("새로고침", "Refresh", "更新", "刷新"),

    # ---- file dialogs
    "dlg.pick_audio": ("음악 파일 선택", "Select a music file", "音楽ファイルを選択", "选择音乐文件"),
    "ft.audio": ("오디오", "Audio", "オーディオ", "音频"),
    "ft.all": ("모든 파일", "All files", "すべてのファイル", "所有文件"),
    "dlg.save_as": ("저장 위치", "Save location", "保存場所", "保存位置"),
    "ft.osz": ("osu! 비트맵", "osu! beatmap", "osu! ビートマップ", "osu! 谱面"),
    "dlg.open_osz": ("채보(.osz) 열기", "Open chart (.osz)", "譜面(.osz)を開く", "打开谱面(.osz)"),

    # ---- validation messages
    "msg.check": ("확인", "Notice", "確認", "提示"),
    "err.no_audio": ("음악 파일을 선택해 주세요.", "Please select a music file.",
                     "音楽ファイルを選択してください。", "请选择音乐文件。"),
    "err.no_diff": ("난이도를 하나 이상 선택해 주세요.", "Select at least one difficulty.",
                    "難易度を1つ以上選択してください。", "请至少选择一个难度。"),
    "err.no_env": ("실행 환경을 찾을 수 없습니다.\n{python}\n{script}",
                   "Could not find the runtime environment.\n{python}\n{script}",
                   "実行環境が見つかりません。\n{python}\n{script}", "找不到运行环境。\n{python}\n{script}"),
    "err.bad_bpm": ("BPM은 0보다 큰 숫자여야 합니다.", "BPM must be a number greater than 0.",
                    "BPMは0より大きい数値にしてください。", "BPM 必须是大于 0 的数字。"),
    "err.bad_url": ("유튜브 URL을 입력해 주세요. (https://... 형태)", "Enter a YouTube URL (https://...).",
                    "YouTubeのURLを入力してください (https://...)。", "请输入 YouTube 链接 (https://...)。"),
    "err.no_tools": ("yt-dlp.exe / ffmpeg.exe 를 찾을 수 없습니다.\n{path}",
                     "Could not find yt-dlp.exe / ffmpeg.exe.\n{path}",
                     "yt-dlp.exe / ffmpeg.exe が見つかりません。\n{path}", "找不到 yt-dlp.exe / ffmpeg.exe。\n{path}"),

    # ---- status line / log
    "st.analyzing": ("분석 중... (보컬 분리는 처음엔 오래 걸릴 수 있습니다)",
                     "Analyzing... (the first vocal separation can take a while)",
                     "解析中... (初回のボーカル分離は時間がかかることがあります)",
                     "分析中... (首次分离人声可能需要较长时间)"),
    "st.fetching": ("유튜브에서 가져오는 중...", "Fetching from YouTube...", "YouTubeから取得中...", "正在从 YouTube 获取..."),
    "st.dl_pct": ("다운로드 중... {pct}%", "Downloading... {pct}%", "ダウンロード中... {pct}%", "下载中... {pct}%"),
    "st.sep_pct": ("보컬 분리 중... {pct}%", "Separating vocals... {pct}%", "ボーカル分離中... {pct}%", "分离人声中... {pct}%"),
    "st.dl_done": ("가져오기 완료! 이제 '채보 생성'을 누르세요.", "Import complete! Now press 'Generate chart'.",
                   "取得完了! 「譜面を生成」を押してください。", "获取完成! 现在点击“生成谱面”。"),
    "st.dl_fail": ("가져오기 실패 (URL이나 영상 공개 여부를 확인하세요)",
                   "Import failed (check the URL and that the video is public)",
                   "取得に失敗 (URLと動画の公開設定を確認してください)", "获取失败 (请检查链接及视频是否公开)"),
    "st.gen_done": ("완료! 오른쪽 플레이어에서 ▶ 시작을 눌러 테스트해 보세요.",
                    "Done! Press ▶ Start in the player on the right to try it.",
                    "完了! 右のプレイヤーで ▶ 開始 を押して試してください。",
                    "完成! 请在右侧播放器点击 ▶ 开始试玩。"),
    "st.gen_fail": ("실패 또는 중지됨", "Failed or stopped", "失敗または停止しました", "失败或已停止"),
    "log.stopped": ("중지했습니다.", "Stopped.", "停止しました。", "已停止。"),
    "log.launch_fail": ("실행 실패: {err}", "Failed to start: {err}", "起動に失敗: {err}", "启动失败: {err}"),

    # ---- game panel
    "game.placeholder": ("채보를 만들거나 라이브러리에서 불러오세요", "Generate a chart or load one from the library",
                         "譜面を生成するか、ライブラリから読み込んでください", "请生成谱面，或从曲库载入"),
    "game.start": ("▶ 시작", "▶ Start", "▶ 開始", "▶ 开始"),
    "game.again": ("↻ 다시", "↻ Retry", "↻ やり直す", "↻ 重来"),
    "game.speed": ("노트 속도", "Note speed", "ノーツ速度", "音符速度"),
    "game.volume": ("음악 음량", "Music volume", "音楽の音量", "音乐音量"),
    "game.judge": ("판정 (넉넉↔빡빡)", "Judgment (loose↔strict)", "判定 (甘い↔厳しい)", "判定 (宽松↔严格)"),
    "game.sync": ("싱크(ms)", "Sync (ms)", "同期(ms)", "同步(ms)"),
    "game.countdown": ("카운트다운(초)", "Countdown (s)", "カウントダウン(秒)", "倒计时(秒)"),
    "game.auto": ("퍼펙트 오토", "Perfect auto", "パーフェクトオート", "完美自动"),
    "game.note_shape": ("노트 모양", "Note shape", "ノーツの形", "音符形状"),
    "note.ring": ("링", "Ring", "リング", "圆环"),
    "note.classic": ("직사각형", "Rectangle", "長方形", "矩形"),
    "game.effect": ("타격 이펙트", "Hit effect", "ヒットエフェクト", "打击特效"),
    "fx.ripple": ("물결", "Ripple", "波紋", "波纹"),
    "fx.burst": ("터지는 효과", "Burst", "バースト", "爆裂"),
    "game.keyset": ("키 설정", "Key bindings", "キー設定", "按键设置"),
    "game.hint": ("소리가 늦게 들리면 싱크를 +로, ESC 일시정지 · R 다시 시작",
                  "If the sound is late, raise Sync (+). ESC: pause · R: restart",
                  "音が遅れて聞こえる場合は同期を + に。ESC: 一時停止 · R: やり直し",
                  "若声音偏晚，请将同步调为 +。ESC: 暂停 · R: 重来"),
    "game.keys": ("키: {keys}", "Keys: {keys}", "キー: {keys}", "按键: {keys}"),
    "game.diff_item": ("{version}  ({n}노트)", "{version}  ({n} notes)", "{version}  ({n}ノーツ)", "{version}  ({n}个音符)"),
    "game.err_osz": ("채보 또는 음악 파일이 없는 .osz 입니다.", "This .osz has no chart or music file.",
                     "この .osz には譜面または音楽ファイルがありません。", "此 .osz 中没有谱面或音乐文件。"),
    "game.st_load_fail": ("채보를 불러오지 못했습니다: {err}", "Could not load the chart: {err}",
                          "譜面を読み込めませんでした: {err}", "无法载入谱面: {err}"),
    "game.st_loaded": ("불러옴: {name}", "Loaded: {name}", "読み込み完了: {name}", "已载入: {name}"),
    "game.st_audio_fail": ("오디오를 초기화하지 못했습니다: {err}", "Could not initialize audio: {err}",
                           "オーディオを初期化できませんでした: {err}", "无法初始化音频: {err}"),
    "game.st_play_fail": ("음악을 재생하지 못했습니다: {err}", "Could not play the music: {err}",
                          "音楽を再生できませんでした: {err}", "无法播放音乐: {err}"),
    "game.st_need_chart": ("먼저 채보를 불러와 주세요.", "Load a chart first.", "先に譜面を読み込んでください。", "请先载入谱面。"),
    "keydlg.title": ("키 설정", "Key bindings", "キー設定", "按键设置"),
    "keydlg.cancel": ("Esc: 취소", "Esc: cancel", "Esc: キャンセル", "Esc: 取消"),
    "keydlg.prompt": ("레인 {i} / {n} — 키를 누르세요…", "Lane {i} / {n} — press a key…",
                      "レーン {i} / {n} — キーを押してください…", "轨道 {i} / {n} — 请按键…"),

    # ---- play field
    "cv.load_hint": ("오른쪽 위에서 채보를 불러오세요", "Load a chart from the top right",
                     "右上から譜面を読み込んでください", "请在右上方载入谱面"),
    "cv.press_start": ("▶ 시작을 누르세요", "Press ▶ Start", "▶ 開始 を押してください", "请点击 ▶ 开始"),
    "cv.paused": ("일시정지", "Paused", "一時停止", "已暂停"),
    "cv.pause_keys": ("Enter 계속하기  ·  R 다시 시작  ·  Q 곡 선택",
                      "Enter: resume  ·  R: restart  ·  Q: back to song",
                      "Enter: 再開  ·  R: やり直し  ·  Q: 曲選択", "Enter: 继续  ·  R: 重来  ·  Q: 返回选曲"),
    "cv.accuracy": ("정확도 {acc}%   ·   MAX COMBO {combo}", "Accuracy {acc}%   ·   MAX COMBO {combo}",
                    "精度 {acc}%   ·   MAX COMBO {combo}", "准确率 {acc}%   ·   MAX COMBO {combo}"),
    "cv.result_keys": ("R 다시 시작  ·  ■ 로 곡 선택", "R: restart  ·  ■: back to song",
                       "R: やり直し  ·  ■: 曲選択", "R: 重来  ·  ■: 返回选曲"),
}

_ORDER = ("ko", "en", "ja", "zh")
_lang = DEFAULT


def detect_lang():
    """Language of the Windows UI: ko / ja / zh, otherwise English."""
    try:
        primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
    except (AttributeError, OSError):
        return DEFAULT
    return {0x12: "ko", 0x11: "ja", 0x04: "zh", 0x09: "en"}.get(primary, DEFAULT)


def set_lang(code):
    global _lang
    _lang = code if code in LANGS else DEFAULT


def get_lang():
    return _lang


def t(key, **kw):
    text = _T[key][_ORDER.index(_lang)]
    return text.format(**kw) if kw else text


def keys():
    return list(_T)


def raw(key):
    """All four translations of a key, in ko/en/ja/zh order (used by the tests)."""
    return dict(zip(_ORDER, _T[key]))
