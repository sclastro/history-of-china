#!/usr/bin/env python3
"""重新生成 README.md 嘅索引表（成語一覽 + 分期統計 + 文獻貢獻統計）。

README 由「<!-- INDEX:START -->」同「<!-- INDEX:END -->」兩個標記包住嘅部分
會被整段取代；標記以外嘅手寫內容一概保留。

用法：python3 scripts/build_index.py
"""
import re
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
START, END = "<!-- INDEX:START -->", "<!-- INDEX:END -->"


def load(p):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def year_label(v):
    if isinstance(v, int):
        return f"前 {abs(v)}" if v < 0 else str(v)
    if isinstance(v, str):
        m = re.search(r"-?\d+", v)
        if m:
            n = int(m.group())
            return f"約前 {abs(n)}" if n < 0 else f"約 {n}"
    return "—"


def main() -> int:
    states = {s["id"]: s for s in load(ROOT / "data/states.yaml")}
    sources = {s["id"]: s for s in load(ROOT / "data/sources.yaml")}
    periods = load(ROOT / "data/periods.yaml")
    period_by_id = {p["id"]: p for p in periods}
    period_order = {p["id"]: i for i, p in enumerate(periods)}

    idioms = [load(p) for p in sorted((ROOT / "idioms").glob("*/profile.yaml"))]
    events = [load(p) for p in sorted((ROOT / "events").glob("*.yaml"))]
    people = [load(p) for p in sorted((ROOT / "people").glob("*.yaml"))]

    def key(d):
        y = d.get("year")
        if isinstance(y, int):
            return (y, 0, d["id"])
        return (period_by_id[d["period"]]["end"], 1, d["id"])

    idioms.sort(key=key)

    lines = [START, ""]

    # ── 分期統計 ──
    lines += ["## 收錄統計", "",
              f"目前收錄 **{len(idioms)}** 條成語、**{len(events)}** 個事件、"
              f"**{len(people)}** 個人物。", "",
              "| 分期 | 起訖 | 成語 | 事件 |", "|---|---|---:|---:|"]
    ic = Counter(d["period"] for d in idioms)
    ec = Counter(e["period"] for e in events)
    for p in periods:
        lines.append(f'| {p["name"]} | 前 {abs(p["start"])} – 前 {abs(p["end"])} '
                     f'| {ic.get(p["id"], 0)} | {ec.get(p["id"], 0)} |')
    lines.append("")

    # ── 可信度分佈 ──
    rc = Counter(d["reliability"] for d in idioms)
    lines += ["| 史料可信度 | 條數 | 判準 |", "|---|---:|---|"]
    hints = {
        "信史": "同期或近期文獻互證，可繫年繫人",
        "大體可信": "主源可信，細節有後世增飾",
        "孤證": "僅一書所載，別無旁證",
        "後世附會": "晚出，或與早期文獻／出土材料相牴",
        "寓言": "諸子所設之譬喻，本無其事",
    }
    for r in ["信史", "大體可信", "孤證", "後世附會", "寓言"]:
        lines.append(f"| {r} | {rc.get(r, 0)} | {hints[r]} |")
    lines.append("")

    # ── 文獻貢獻 ──
    primary = Counter()
    for d in idioms:
        dy = d.get("dianyuan") or []
        if dy:
            primary[dy[0].get("source")] += 1
    lines += ["## 各書貢獻（典源計）", "", "| 文獻 | 層 | 條數 |", "|---|:-:|---:|"]
    for sid, n in primary.most_common():
        s = sources.get(sid, {})
        lines.append(f'| 《{s.get("name", sid)}》 | {s.get("layer", "—")} | {n} |')
    lines.append("")

    # ── 成語一覽 ──
    lines += ["## 成語一覽", "",
              "| 成語 | 年 | 分期 | 類型 | 典源 | 可信度 | 條目 |",
              "|---|---|---|---|---|---|---|"]
    for d in idioms:
        dy = (d.get("dianyuan") or [{}])[0]
        src = sources.get(dy.get("source"), {})
        locus = dy.get("locus", "")
        st = "、".join(states[s]["name"] for s in d.get("states", []) if s in states)
        lines.append(
            f'| {d["idiom"]["zh"]} | {year_label(d.get("year"))} '
            f'| {period_by_id[d["period"]]["name"].split("・")[0]} '
            f'| {"寓言" if d["type"] == "parable" else "史事"} '
            f'| 《{src.get("name", "")}》{locus} | {d["reliability"]} '
            f'| [{d["id"]}](idioms/{d["id"]}/{d["id"]}.md) |'
        )
    lines += ["", END]

    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8") if readme.exists() else ""
    block = "\n".join(lines)
    if START in text and END in text:
        text = re.sub(re.escape(START) + r".*?" + re.escape(END), block, text, flags=re.S)
    else:
        text = (text.rstrip() + "\n\n" + block + "\n") if text else block + "\n"
    readme.write_text(text, encoding="utf-8")
    print(f"README 索引已更新：{len(idioms)} 條成語、{len(events)} 個事件、{len(people)} 個人物")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
