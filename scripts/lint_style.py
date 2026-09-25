#!/usr/bin/env python3
"""檢查事件稿是否符合 docs/translation-style.md 中可機械檢查的部分：
「什麼」須作「甚麼」；narrative／significance 引號內只放原文或成語；narrative 殘留的文言虛詞。
「之」字常見於現代書面語（一箭之仇、邯鄲之圍），只作提示，須人手判斷。
引號內容以本事件 original 及 verify_original.py 已快取的維基文庫全文比對，故宜先執行該腳本。

用法：python3 scripts/lint_style.py events/bi-zhi-zhan.yaml ...
"""
import re, sys, tempfile
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
IDIOMS = {yaml.safe_load(p.read_text())["idiom"]["zh"] for p in ROOT.glob("idioms/*/profile.yaml")}
CACHE = Path(tempfile.gettempdir()) / "wikisource-cache"
PUNCT = re.compile(r"[\s，。、；：？！「」『』（）…—]")
XU = "乎矣焉豈蓋遂乃"
ZHI_OK = "後前間中一外內下上所際類時處餘長首"

def corpus(ev):
    """事件本身的原文加上已抓取的維基文庫全文，用來判斷引號內是否原文。"""
    parts = [c.get("quote", "") for c in ev.get("original") or []]
    parts += [p.read_text() for p in CACHE.glob("*.txt")]
    return PUNCT.sub("", "".join(parts))

if len(sys.argv) < 2:
    sys.exit(__doc__)
for fn in sys.argv[1:]:
    ev = yaml.safe_load(open(fn))
    text_all = corpus(ev)
    notes = []
    fields = {"narrative": ev.get("narrative", ""), "significance": ev.get("significance", "")}
    for i, c in enumerate(ev.get("original") or []):
        fields[f"original[{i}].translation"] = c.get("translation", "")
    for k, v in fields.items():
        if "什麼" in v:
            notes.append(f"{k}：用了「什麼」")
        # 引號內容：成語名、或原文可查者方可；翻譯欄內的直接引語不在此限
        if not k.startswith("original"):
            outside = re.sub(r"「[^」]*」|（白話：[^）]*）", "", v)
            for q in re.findall(r"「([^」]*)」", v):
                if q in IDIOMS or PUNCT.sub("", q) in text_all:
                    continue
                notes.append(f"{k}：引號內非原文「{q}」")
            if k == "narrative":
                hits = sorted({ch for ch in outside if ch in XU})
                hits += [f"之{m.group(1)}" for m in re.finditer(r"之(.)", outside) if m.group(1) not in ZHI_OK]
                if hits:
                    notes.append(f"narrative：引號外有文言虛詞 {''.join(hits)}（須人手判斷）")
    print(f"=== {ev['name']}（{Path(fn).stem}）")
    for n in notes or ["無問題"]:
        print("  " + n)
