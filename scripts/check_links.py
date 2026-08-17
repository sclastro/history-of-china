#!/usr/bin/env python3
"""覆檢條目中嘅外部連結係咪仍然有效（需連網，約一至兩分鐘）。

檢查兩類：
    ctext_urn  →  https://ctext.org/<書>/<篇章>/zh
    references →  條目 references[] 所列嘅網址（含教育部成語典）

ctext.org 會擋非瀏覽器嘅 User-Agent，故一律帶瀏覽器 UA；
仍然回 403 者標為「無法判定」而唔算失敗——請人手覆核。

用法：python3 scripts/check_links.py [--slow 秒數]
"""
import argparse
import sys
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def load(p):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_urls():
    """回傳 OrderedDict：url → 引用佢嘅條目路徑清單。"""
    urls = OrderedDict()

    def add(url, where):
        urls.setdefault(url, []).append(where)

    def walk_citations(items, where):
        for c in items or []:
            urn = c.get("ctext_urn")
            if urn and urn.startswith("ctp:"):
                add(f"https://ctext.org/{urn[4:]}/zh", where)

    for p in sorted((ROOT / "idioms").glob("*/profile.yaml")):
        d = load(p)
        where = str(p.relative_to(ROOT))
        walk_citations(d.get("dianyuan"), where)
        walk_citations(d.get("variants"), where)
        for u in d.get("references") or []:
            add(u, where)
        cry = d.get("crystallisation") or {}
        if cry.get("moe_id"):
            add(f"https://dict.idioms.moe.edu.tw/idiomView.jsp?ID={cry['moe_id']}"
                f"&webMd=1&la=0", where)

    for sub, field in (("events", "sources"), ("people", "sources")):
        for p in sorted((ROOT / sub).glob("*.yaml")):
            d = load(p)
            where = str(p.relative_to(ROOT))
            walk_citations(d.get(field), where)
            walk_citations(d.get("variants"), where)

    for s in load(ROOT / "data/sources.yaml"):
        if s.get("ctext"):
            add(f"https://ctext.org/{s['ctext']}/zh", "data/sources.yaml")
    return urls


def check(url, timeout=20):
    """回傳 (狀態, 說明)：ok / bad / unknown。"""
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return ("ok", resp.status)
    except urllib.error.HTTPError as ex:
        if ex.code in (403, 429):
            return ("unknown", f"HTTP {ex.code}（站方擋自動請求，請人手覆核）")
        return ("bad", f"HTTP {ex.code}")
    except Exception as ex:                       # 逾時、DNS、TLS 等
        return ("unknown", type(ex).__name__)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slow", type=float, default=0.4,
                    help="每個請求之間嘅間隔秒數，預設 0.4")
    args = ap.parse_args()

    urls = collect_urls()
    print(f"共 {len(urls)} 個不重複網址，開始覆檢…\n")

    bad, unknown = [], []
    for i, (url, wheres) in enumerate(urls.items(), 1):
        status, info = check(url)
        mark = {"ok": "✓", "bad": "✗", "unknown": "?"}[status]
        print(f"{mark} [{i}/{len(urls)}] {url}" + ("" if status == "ok" else f"  — {info}"))
        if status == "bad":
            bad.append((url, info, wheres))
        elif status == "unknown":
            unknown.append((url, info, wheres))
        time.sleep(args.slow)

    print()
    if bad:
        print(f"── 失效（{len(bad)}）──")
        for url, info, wheres in bad:
            print(f"✗ {url}  — {info}")
            for w in sorted(set(wheres)):
                print(f"      引用於 {w}")
    if unknown:
        print(f"\n── 無法判定（{len(unknown)}）——請人手覆核 ──")
        for url, info, _ in unknown:
            print(f"? {url}  — {info}")
    if not bad:
        print("冇發現失效連結。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
