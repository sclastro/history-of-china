#!/usr/bin/env python3
"""經 Poe API 把事件改寫為現代書面語（見 docs/translation-style.md）。

刻意**逐條、順序**處理：任何時候只有一個請求在進行，避免一次過耗盡 Poe 的額度。
輸出寫入 --out 目錄供人手覆核，不會直接覆蓋 events/。

用法：
  export POE_API_KEY=...                       # 只從環境變數讀取，切勿寫入 repo
  python3 scripts/poe_rewrite.py --list-models # 列出可用的 Claude Opus 型號
  python3 scripts/poe_rewrite.py --model <型號> --out /tmp/rewrite bi-zhi-zhan
  python3 scripts/poe_rewrite.py --model <型號> --out /tmp/rewrite --all --limit 5
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.poe.com/v1"
EXAMPLE = "cheng-pu-zhi-zhan"
REWRITTEN = ("narrative", "original", "significance")


def call(path, body=None):
    key = os.environ.get("POE_API_KEY")
    if not key:
        sys.exit("未設定環境變數 POE_API_KEY。")
    req = urllib.request.Request(
        f"{API}/{path}",
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def chat(model, content):
    """以串流方式請求：生成期間持續有資料傳回，避免長時間靜默被代理或網關斷線。"""
    key = os.environ.get("POE_API_KEY")
    if not key:
        sys.exit("未設定環境變數 POE_API_KEY。")
    body = {"model": model, "stream": True, "stream_options": {"include_usage": True},
            "messages": [{"role": "user", "content": content}]}
    req = urllib.request.Request(
        f"{API}/chat/completions", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    parts, usage = [], {}
    with urllib.request.urlopen(req, timeout=600) as r:
        for raw in r:
            line = raw.decode().strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            chunk = json.loads(data)
            usage = chunk.get("usage") or usage
            for c in chunk.get("choices") or []:
                parts.append((c.get("delta") or {}).get("content") or "")
    return "".join(parts), usage


def list_models():
    ids = [m["id"] for m in call("models")["data"]]
    for m in sorted(i for i in ids if re.search(r"opus", i, re.I)):
        print(m)


def prompt(event_id):
    style = (ROOT / "docs/translation-style.md").read_text()
    example = (ROOT / f"events/{EXAMPLE}.yaml").read_text()
    target = (ROOT / f"events/{event_id}.yaml").read_text()
    return f"""你是先秦史編輯。請按以下標準，改寫目標事件 YAML 的 narrative、significance，並新增 original 欄。

{style}

## 已完成的範例

```yaml
{example}
```

## 目標事件

```yaml
{target}
```

要求：
- 只輸出一個完整的 YAML 代碼塊，不要任何說明文字。
- narrative、original、significance 以外的欄位原封不動。
- original 的 quote 必須逐字照錄《左傳》《史記》等原典，不可自行改寫或杜撰；無把握者寧缺毋濫。
- 內容只依原有 narrative 與原典，不可添加史料沒有的情節。"""


def rewrite(event_id, model, out):
    src = yaml.safe_load((ROOT / f"events/{event_id}.yaml").read_text())
    text, usage = chat(model, prompt(event_id))
    m = re.search(r"```(?:yaml)?\n(.*?)```", text, re.S)
    body = m.group(1) if m else text
    new = yaml.safe_load(body)
    changed = [k for k in src if k not in REWRITTEN and src[k] != new.get(k)]
    if changed:
        print(f"  ! {event_id}：模型改動了不應改的欄位 {changed}，已照原值還原")
        for k in changed:
            new[k] = src[k]
        body = None
    path = out / f"{event_id}.yaml"
    path.write_text(body if body else yaml.safe_dump(new, allow_unicode=True, sort_keys=False, width=1000))
    print(f"✓ {event_id} → {path}（tokens：{usage.get('total_tokens', '?')}）", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--model")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--all", action="store_true", help="處理全部尚未有 original 欄的事件")
    ap.add_argument("--limit", type=int, default=0, help="最多處理幾條（0 為不限）")
    ap.add_argument("--list-models", action="store_true")
    a = ap.parse_args()
    if a.list_models:
        return list_models()
    if not (a.model and a.out):
        ap.error("須指定 --model 及 --out")
    ids = a.ids
    if a.all:
        ids = [p.stem for p in sorted((ROOT / "events").glob("*.yaml"))
               if "original" not in yaml.safe_load(p.read_text())]
    if a.limit:
        ids = ids[:a.limit]
    a.out.mkdir(parents=True, exist_ok=True)
    for i in ids:                      # 逐條順序執行，不並行
        if (a.out / f"{i}.yaml").exists():
            print(f"- {i} 已有輸出，略過")
            continue
        rewrite(i, a.model, a.out)


if __name__ == "__main__":
    main()
