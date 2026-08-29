#!/usr/bin/env python3
"""為每條成語預先生成粵語發音音檔（assets/audio/<id>.mp3）。

音檔喺「建置時」生成並存為靜態檔案，網站只負責播放，
所以無須任何 API key、無逐次費用、無延遲，而且每部機聽到嘅完全一樣。

引擎：Google Translate 嘅粵語 TTS（`gtts`，lang="yue"），免費、無須 key。

    pip install gtts

點解唔用瀏覽器內置嘅 speechSynthesis：粵語 voice 嘅覆蓋率唔穩——
iOS／macOS 有 Sinji、Android 一般有 Google 粵語、Windows 有 zh-HK，
但桌面 Linux 同部分 Chrome 一個粵語 voice 都無，撳落去會靜英英乜都無。
做參考網站唔應該有呢種情況，所以寧願付出約 550 KB 換確定性。

點解唔用 Poe 嗰批 TTS：ElevenLabs、Gemini TTS 官方語言表都無粵語，
實測讀出嚟係普通話；MiniMax 雖然聲稱支援，實測亦唔係地道粵語。

用法：
    python3 scripts/build_audio.py                  # 只生成尚未存在者
    python3 scripts/build_audio.py --force          # 全部重新生成
    python3 scripts/build_audio.py tui-bi-san-she   # 只做指定條目
    python3 scripts/build_audio.py --list           # 只列出粵拼，唔生成

破音字：TTS 未必讀啱成語裡嘅異讀（例如「上下其手」嘅「上」）。
每條成語嘅 profile.yaml 都有 jyutping 欄，網頁上會一併顯示，
可以用嚟核對讀音；讀錯者請記錄喺 docs/framework.md 待處理。

依賴：pyyaml、gtts
"""
import argparse
import io
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
IDIOMS_DIR = ROOT / "idioms"
AUDIO_DIR = ROOT / "assets" / "audio"
LANG = "yue"


def synthesize(text: str) -> bytes:
    """用 Google Translate 粵語 TTS 合成，回傳 MP3 位元組。"""
    try:
        from gtts import gTTS
    except ImportError as exc:                       # pragma: no cover
        raise RuntimeError("未安裝 gtts，請先 `pip install gtts`") from exc

    buf = io.BytesIO()
    gTTS(text=text, lang=LANG).write_to_fp(buf)
    audio = buf.getvalue()
    # 裸 MPEG frame（gtts）或帶 ID3 標頭都算數
    if not (audio[:3] == b"ID3" or audio[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
        raise RuntimeError(f"合成結果唔係 MP3（前 4 位元組 {audio[:4]!r}）")
    if len(audio) < 2000:
        raise RuntimeError(f"音檔過短（{len(audio)} bytes），可能係錯誤回應")
    return audio


def main() -> int:
    ap = argparse.ArgumentParser(description="生成成語的粵語發音音檔")
    ap.add_argument("ids", nargs="*", help="只處理指定的條目 id（預設全部）")
    ap.add_argument("--force", action="store_true", help="即使音檔已存在亦重新生成")
    ap.add_argument("--list", action="store_true", help="只列出成語與粵拼，唔生成音檔")
    args = ap.parse_args()

    entries = []
    for profile in sorted(IDIOMS_DIR.glob("*/profile.yaml")):
        with open(profile, encoding="utf-8") as f:
            d = yaml.safe_load(f)
        if not args.ids or d["id"] in args.ids:
            entries.append(d)

    if args.list:
        for d in entries:
            print(f"{d['id']:26s} {d['idiom']['zh']}　{d['idiom'].get('jyutping', '（無粵拼）')}")
        return 0

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    made = skipped = failed = 0
    for d in entries:
        iid, zh = d["id"], d["idiom"]["zh"]
        out = AUDIO_DIR / f"{iid}.mp3"
        if out.exists() and not args.force:
            skipped += 1
            continue
        for attempt in range(1, 4):
            try:
                audio = synthesize(zh)
                out.write_bytes(audio)
                print(f"✓  {iid:26s} 「{zh}」  {len(audio) / 1024:.0f} KB　"
                      f"粵 {d['idiom'].get('jyutping', '')}", flush=True)
                made += 1
                time.sleep(0.4)          # 對 Google 溫和一啲
                break
            except (OSError, RuntimeError) as exc:
                if attempt == 3:
                    print(f"✗  {iid:26s} 「{zh}」  {type(exc).__name__}: {exc}",
                          file=sys.stderr, flush=True)
                    failed += 1
                else:
                    time.sleep(2 * attempt)

    total = sum(1 for _ in AUDIO_DIR.glob("*.mp3"))
    size = sum(p.stat().st_size for p in AUDIO_DIR.glob("*.mp3")) / 1024
    print(f"\n新生成 {made}，已存在略過 {skipped}，失敗 {failed}")
    print(f"assets/audio/ 現有 {total} 個音檔，共 {size:.0f} KB")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
