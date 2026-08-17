#!/usr/bin/env python3
"""由 idioms / events / people / data 生成全站靜態 HTML。

生成：
    index.html      總覽格陣（全部成語，可篩選）
    timeline.html   時間 × 列國 二維年表（手機退化為按分期收合的列表）
    idioms.html     成語索引（可按分期／列國／類型／可信度／概念切換分組）
    events.html     編年大事表
    people.html     人物列表（按國分組）
    sources.html    文獻譜系（含各書貢獻成語數，由數據自動統計）
    idioms/<id>/index.html   成語詳頁（四層考據 + 論述文章）
    404.html / robots.txt / sitemap.xml / .nojekyll
    assets/search-index.js   ⌘K 全站搜尋索引

用法：python3 scripts/build_site.py
"""
import html
import json
import re
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SITE_URL = "https://cc-chunqiu.vercel.app"
SITE_NAME = "春秋戰國成語知識庫"
SITE_DESC = "以四字成語為主軸，重新組織春秋戰國五百五十年的歷史事件、人物與概念；每條成語分本事、典源、語形定型、史料可信度四層考據。"

TL_START, TL_END = -775, -218       # 年表左右邊界（略寬於 -770 – -221）


# ────────────────────────── 載入 ──────────────────────────

def load(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_all():
    data = {
        "states": {s["id"]: s for s in load(ROOT / "data/states.yaml")},
        "sources": {s["id"]: s for s in load(ROOT / "data/sources.yaml")},
        "periods": load(ROOT / "data/periods.yaml"),
        "idioms": {},
        "events": {},
        "people": {},
    }
    for p in sorted((ROOT / "idioms").glob("*/profile.yaml")):
        d = load(p)
        d["_md"] = (p.parent / f"{d['id']}.md").read_text(encoding="utf-8")
        data["idioms"][d["id"]] = d
    for p in sorted((ROOT / "events").glob("*.yaml")):
        d = load(p)
        data["events"][d["id"]] = d
    for p in sorted((ROOT / "people").glob("*.yaml")):
        d = load(p)
        data["people"][d["id"]] = d
    data["period_by_id"] = {p["id"]: p for p in data["periods"]}
    return data


# ────────────────────────── 小工具 ──────────────────────────

BOLD = re.compile(r"\*\*([^*]+)\*\*")


def e(text):
    return html.escape(str(text if text is not None else ""))


def rich(text):
    """條目欄位容許用 **粗體** 強調；先跳脫再轉換，避免注入。"""
    return BOLD.sub(r"<strong>\1</strong>", e(text))


def year_num(v):
    """把 year 欄化為整數以供排序、定位；不可考者回傳 None。"""
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        m = re.search(r"-?\d+", v)
        if m:
            return int(m.group())
    return None


def year_label(v):
    """把 -632 顯示為「前 632」。"""
    n = year_num(v)
    if n is None:
        return "年代不詳"
    return f"前 {abs(n)}" if n < 0 else str(n)


def ctext_url(urn):
    if not urn or not urn.startswith("ctp:"):
        return None
    return f"https://ctext.org/{urn[4:]}/zh"


def sort_key_idiom(d):
    """寓言型無確年，用分期結束年排序，令其落喺該期史事條目之後。"""
    n = year_num(d.get("year"))
    if n is not None:
        return (n, 0, d["id"])
    return (PERIOD_END.get(d.get("period"), 0), 1, d["id"])


PERIOD_END = {}


# ────────────────────────── Markdown（極簡） ──────────────────────────

INLINE_CODE = re.compile(r"`([^`]+)`")


def inline(text):
    out = e(text)
    out = INLINE_CODE.sub(r"<code>\1</code>", out)
    out = BOLD.sub(r"<strong>\1</strong>", out)
    return out


def markdown(src):
    """支援：# 標題、> 引用、- / 1. 清單、--- 分隔線、段落、**粗體**、`碼`。"""
    lines = src.split("\n")
    out, i = [], 0
    para, quote, ul, ol = [], [], [], []

    def flush():
        nonlocal para, quote, ul, ol
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para = []
        if quote:
            body = "".join(f"<p>{inline(q)}</p>" for q in quote)
            out.append(f"<blockquote>{body}</blockquote>")
            quote = []
        if ul:
            body = "".join(f"<li>{inline(x)}</li>" for x in ul)
            out.append(f"<ul>{body}</ul>")
            ul = []
        if ol:
            body = "".join(f"<li>{inline(x)}</li>" for x in ol)
            out.append(f"<ol>{body}</ol>")
            ol = []

    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            flush()
        elif ln.startswith("#"):
            flush()
            level = len(ln) - len(ln.lstrip("#"))
            out.append(f"<h{level}>{inline(ln[level:].strip())}</h{level}>")
        elif ln.strip() in ("---", "***"):
            flush()
            out.append("<hr>")
        elif ln.startswith(">"):
            if para or ul or ol:
                flush()
            quote.append(ln.lstrip("> ").strip())
        elif re.match(r"^\s*[-*]\s+", ln):
            if para or quote or ol:
                flush()
            ul.append(re.sub(r"^\s*[-*]\s+", "", ln))
        elif re.match(r"^\s*\d+\.\s+", ln):
            if para or quote or ul:
                flush()
            ol.append(re.sub(r"^\s*\d+\.\s+", "", ln))
        else:
            if quote or ul or ol:
                flush()
            para.append(ln.strip())
        i += 1
    flush()
    return "\n".join(out)


# ────────────────────────── 版面外框 ──────────────────────────

NAV = [
    ("index.html", "總覽"),
    ("timeline.html", "年表"),
    ("idioms.html", "成語索引"),
    ("events.html", "大事"),
    ("people.html", "人物"),
    ("sources.html", "文獻"),
]


def page(title, body, *, current="", depth=0, desc=None, canonical=""):
    up = "../" * depth
    desc = desc or SITE_DESC
    nav = "".join(
        '<a href="%s%s"%s>%s</a>' % (
            up, href, ' class="current"' if href == current else "", label)
        for href, label in NAV
    )
    full_title = title if title == SITE_NAME else f"{title}｜{SITE_NAME}"
    canon = f"{SITE_URL}/{canonical}" if canonical else SITE_URL
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canon)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{e(full_title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canon)}">
<link rel="stylesheet" href="{up}assets/style.css">
</head>
<body>
<header class="site-header"><div class="inner">
  <a class="brand" href="{up}index.html">
    <span class="brand-mark">鼎</span>
    <span class="brand-text">
      <span class="title">春秋戰國成語知識庫</span>
      <span class="subtitle">前 770 – 前 221</span>
    </span>
  </a>
  <nav class="site-nav">{nav}</nav>
  <button class="search-trigger" id="searchBtn">搜尋 <kbd>/</kbd></button>
</div></header>

{body}

<footer class="site-footer"><div class="inner">
  <span>共 @@N_IDIOMS@@ 條成語・@@N_EVENTS@@ 個事件・@@N_PEOPLE@@ 個人物</span>
  <a href="{up}docs/design.md">四層考據原則</a>
  <a href="{up}docs/sources.md">引用規範</a>
  <a href="{up}docs/framework.md">收錄骨架</a>
  <span>原文引自公有領域典籍，白話為自譯</span>
</div></footer>

<div class="cmdk-backdrop" id="cmdkBg"></div>
<div class="cmdk" id="cmdk">
  <input type="search" id="cmdkInput" placeholder="搜尋成語、事件、人物、文獻…" autocomplete="off">
  <div class="cmdk-results" id="cmdkResults"></div>
</div>
<script src="{up}assets/search-index.js"></script>
<script>
(function () {{
  var base = "{up}";
  var bg = document.getElementById('cmdkBg'), box = document.getElementById('cmdk');
  var input = document.getElementById('cmdkInput'), results = document.getElementById('cmdkResults');
  var sel = 0, shown = [];
  function open() {{
    bg.classList.add('open'); box.classList.add('open');
    document.body.classList.add('cmdk-open'); input.value = ''; render(''); input.focus();
  }}
  function close() {{
    bg.classList.remove('open'); box.classList.remove('open');
    document.body.classList.remove('cmdk-open');
  }}
  function render(q) {{
    q = q.trim().toLowerCase();
    shown = q ? SEARCH_INDEX.filter(function (r) {{ return r.k.toLowerCase().indexOf(q) >= 0; }}).slice(0, 40)
              : SEARCH_INDEX.slice(0, 20);
    sel = 0;
    if (!shown.length) {{ results.innerHTML = '<div class="cmdk-empty">搵唔到相符嘅條目。</div>'; return; }}
    results.innerHTML = shown.map(function (r, i) {{
      return '<a href="' + base + r.u + '" class="' + (i === 0 ? 'sel' : '') + '">' +
             '<span class="r-zh">' + r.t + '</span>' +
             '<span class="r-kind">' + r.c + '</span>' +
             '<span class="r-sub">' + (r.s || '') + '</span></a>';
    }}).join('');
  }}
  function move(d) {{
    var links = results.querySelectorAll('a');
    if (!links.length) return;
    links[sel].classList.remove('sel');
    sel = (sel + d + links.length) % links.length;
    links[sel].classList.add('sel');
    links[sel].scrollIntoView({{ block: 'nearest' }});
  }}
  document.getElementById('searchBtn').addEventListener('click', open);
  bg.addEventListener('click', close);
  input.addEventListener('input', function () {{ render(input.value); }});
  input.addEventListener('keydown', function (ev) {{
    if (ev.key === 'ArrowDown') {{ ev.preventDefault(); move(1); }}
    else if (ev.key === 'ArrowUp') {{ ev.preventDefault(); move(-1); }}
    else if (ev.key === 'Enter') {{
      var links = results.querySelectorAll('a');
      if (links[sel]) location.href = links[sel].getAttribute('href');
    }} else if (ev.key === 'Escape') close();
  }});
  document.addEventListener('keydown', function (ev) {{
    var tag = (ev.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea') return;
    if (ev.key === '/' || ((ev.metaKey || ev.ctrlKey) && ev.key === 'k')) {{ ev.preventDefault(); open(); }}
  }});
}})();
</script>
</body>
</html>
"""


# ────────────────────────── 片段 ──────────────────────────

def rel_tag(rel):
    return f'<span class="tag tag-rel" data-rel="{e(rel)}">{e(rel)}</span>'


def type_tag(t):
    return f'<span class="tag tag-type">{"寓言" if t == "parable" else "史事"}</span>'


def idiom_card(d, data, up=""):
    states = "".join(
        f'<span class="tag tag-state">{e(data["states"][s]["name"])}</span>'
        for s in (d.get("states") or []) if s in data["states"]
    )
    per = data["period_by_id"].get(d.get("period"), {})
    return f"""<a class="card" href="{up}idioms/{e(d['id'])}/">
  <span class="zh">{e(d['idiom']['zh'])}</span>
  <span class="meta">{e(year_label(d.get('year')))}・{e(per.get('name', ''))}</span>
  <span class="meaning">{e(d.get('meaning'))}</span>
  <span class="tags">{type_tag(d['type'])}{rel_tag(d['reliability'])}{states}</span>
</a>"""


def cite_line(c, data):
    src = data["sources"].get(c.get("source"), {})
    url = ctext_url(c.get("ctext_urn"))
    book = f'<span class="book">《{e(src.get("name", c.get("source")))}》</span>'
    locus = e(c.get("locus", ""))
    link = f' <a href="{e(url)}" target="_blank" rel="noopener">ctext ↗</a>' if url else ""
    return f"{book}<span>{locus}</span>{link}"


def quote_block(c, data):
    parts = [f'<div class="cite">{cite_line(c, data)}</div>']
    parts.append(f'<div class="original">{e(c.get("quote", ""))}</div>')
    if c.get("translation"):
        parts.append(f'<div class="translation">{e(c["translation"])}</div>')
    if c.get("note"):
        parts.append(f'<div class="note">{e(c["note"])}</div>')
    return f'<div class="quote-block">{"".join(parts)}</div>'


# ────────────────────────── 各頁 ──────────────────────────

def build_index(data):
    idioms = sorted(data["idioms"].values(), key=sort_key_idiom)
    cards = "".join(idiom_card(d, data) for d in idioms)
    periods = "".join(
        f'<button data-f="period" data-v="{e(p["id"])}">{e(p["name"].split("・")[0])}</button>'
        for p in data["periods"]
    )
    rels = "".join(
        f'<button data-f="rel" data-v="{e(r)}">{e(r)}</button>'
        for r in ["信史", "大體可信", "孤證", "後世附會", "寓言"]
    )
    body = f"""<main>
<div class="page-head">
  <h1>春秋戰國成語知識庫</h1>
  <p class="lede">{e(SITE_DESC)}
  每條成語都分清<b>本事</b>（實際發生了什麼）、<b>典源</b>（最早見於哪一段）、
  <b>語形定型</b>（四字形式何時確立）與<b>史料可信度</b>——
  這四者往往相差數百年乃至兩千年。</p>
</div>
<div class="filters" id="filters">
  <span class="label">分期</span>{periods}
  <span class="label" style="margin-left:12px">可信度</span>{rels}
  <button data-f="reset" data-v="">全部</button>
  <span class="spacer"></span>
  <span class="result-count" id="resultCount"></span>
</div>
<div class="grid" id="grid">{cards}</div>
</main>
<script>
(function () {{
  var grid = document.getElementById('grid'), cards = [].slice.call(grid.children);
  var meta = {json.dumps([
        {"period": d.get("period"), "rel": d["reliability"]} for d in idioms
    ], ensure_ascii=False)};
  var active = {{ period: null, rel: null }};
  var count = document.getElementById('resultCount');
  function apply() {{
    var n = 0;
    cards.forEach(function (c, i) {{
      var ok = (!active.period || meta[i].period === active.period) &&
               (!active.rel || meta[i].rel === active.rel);
      c.style.display = ok ? '' : 'none';
      if (ok) n++;
    }});
    count.textContent = '顯示 ' + n + ' / ' + cards.length + ' 條';
  }}
  document.getElementById('filters').addEventListener('click', function (ev) {{
    var b = ev.target.closest('button'); if (!b) return;
    var f = b.dataset.f, v = b.dataset.v;
    if (f === 'reset') {{ active = {{ period: null, rel: null }}; }}
    else {{ active[f] = active[f] === v ? null : v; }}
    [].forEach.call(document.querySelectorAll('#filters button'), function (x) {{
      x.classList.toggle('on', x.dataset.f !== 'reset' && active[x.dataset.f] === x.dataset.v);
    }});
    apply();
  }});
  apply();
}})();
</script>"""
    return page(SITE_NAME, body, current="index.html", canonical="")


def build_timeline(data):
    span = TL_END - TL_START

    def pct(y):
        return max(0, min(100, (y - TL_START) / span * 100))

    # 事件 → 成語
    ev_idioms = {}
    for d in data["idioms"].values():
        ev = (d.get("benshi") or {}).get("event")
        if ev:
            ev_idioms.setdefault(ev, []).append(d)

    # 刻度：每 50 年
    ticks = "".join(
        f'<span class="tick" style="left:{pct(y):.3f}%">前 {abs(y)}</span>'
        for y in range(-750, -200, 50)
    )
    # 分期帶
    segs = ""
    for p in data["periods"]:
        left = pct(p["start"])
        width = pct(p["end"]) - left
        segs += (f'<span class="seg" style="left:{left:.3f}%;width:{width:.3f}%" '
                 f'title="{e(p["name"])}">{e(p["name"].split("・")[0])}</span>')

    lanes = ""
    lane_states = sorted(
        [s for s in data["states"].values() if s.get("lane")],
        key=lambda s: s.get("lane_order", 99),
    )
    for st in lane_states:
        founded = st.get("founded") or TL_START
        ended = st.get("ended") or TL_END
        a, b = pct(max(founded, TL_START)), pct(min(ended, TL_END))
        cls = "span succ" if st.get("successor_of") else "span"
        dots = ""
        for ev in data["events"].values():
            if st["id"] not in (ev.get("states") or []):
                continue
            n = year_num(ev.get("year"))
            if n is None:
                continue
            dots += (f'<button class="tl-dot" data-ev="{e(ev["id"])}" '
                     f'data-type="{e(ev["type"])}" '
                     f'style="left:{pct(n):.3f}%" title="{e(ev["name"])}"></button>')
        lanes += (f'<div class="tl-lane"><span class="name">{e(st["name"])}</span>'
                  f'<span class="{cls}" style="left:{a:.3f}%;width:{max(b - a, 0.4):.3f}%"></span>'
                  f'{dots}</div>')

    ev_json = {}
    for ev in data["events"].values():
        yl = year_label(ev.get("year"))
        if ev.get("year_end"):
            yl += f"–{year_label(ev['year_end'])}"
        ev_json[ev["id"]] = {
            "name": ev["name"],
            "yr": yl,
            "type": ev["type"],
            "rel": ev["reliability"],
            "states": [data["states"][s]["name"] for s in ev.get("states", []) if s in data["states"]],
            "sig": rich(ev.get("significance", "")),
            "idioms": [{"zh": d["idiom"]["zh"], "id": d["id"]}
                       for d in sorted(ev_idioms.get(ev["id"], []), key=sort_key_idiom)],
        }

    # 手機版：按分期收合
    mobile = ""
    for p in data["periods"]:
        evs = sorted(
            [ev for ev in data["events"].values()
             if p["start"] <= (year_num(ev.get("year")) or 0) <= p["end"]],
            key=lambda x: year_num(x.get("year")) or 0,
        )
        if not evs:
            continue
        rows = ""
        for ev in evs:
            ids = "".join(
                f'<a href="idioms/{e(d["id"])}/">{e(d["idiom"]["zh"])}</a>'
                for d in sorted(ev_idioms.get(ev["id"], []), key=sort_key_idiom)
            )
            rows += (f'<div class="row"><span class="yr">{e(year_label(ev.get("year")))}</span>'
                     f'<span class="main"><h3>{e(ev["name"])}</h3>'
                     f'<span class="sub">{e(ev.get("significance", "").replace(chr(42), "")[:90])}…</span>'
                     f'<span class="tags">{ids}</span></span></div>')
        mobile += (f'<details><summary>{e(p["name"])}'
                   f'<span class="yr">前 {abs(p["start"])} – 前 {abs(p["end"])}・{len(evs)} 事</span></summary>'
                   f'<div class="body"><div class="rows">{rows}</div></div></details>')

    body = f"""<main>
<div class="page-head">
  <h1>時間 × 列國</h1>
  <p class="lede">橫軸為公元前 770 至前 221 年，縱軸為列國。
  晉在前 403 年分為趙、魏、韓（三條泳道由此開始），齊在前 386 年由田氏取代姜姓（綠色泳道）。
  點擊圓點可看該事件及其所繫的成語。</p>
</div>
<div class="timeline-wrap"><div class="timeline">
  <div class="tl-periods">{segs}</div>
  <div class="tl-axis">{ticks}</div>
  {lanes}
</div></div>
<div class="tl-detail" id="tlDetail"><span class="placeholder">點擊上方任一圓點，這裡會顯示該事件的說明與相關成語。</span></div>
<div class="tl-mobile">{mobile}</div>
</main>
<script>
var EVENTS = {json.dumps(ev_json, ensure_ascii=False)};
(function () {{
  var box = document.getElementById('tlDetail');
  document.addEventListener('click', function (ev) {{
    var dot = ev.target.closest('.tl-dot'); if (!dot) return;
    var d = EVENTS[dot.dataset.ev]; if (!d) return;
    box.innerHTML = '<h3>' + d.name + '</h3>' +
      '<div class="ev-meta"><span>' + d.yr + '</span><span class="tag">' + d.type + '</span>' +
      '<span class="tag tag-rel" data-rel="' + d.rel + '">' + d.rel + '</span>' +
      d.states.map(function (s) {{ return '<span class="tag tag-state">' + s + '</span>'; }}).join('') +
      '</div><div class="ev-sig">' + d.sig + '</div>' +
      (d.idioms.length ? '<div class="ev-idioms">' + d.idioms.map(function (i) {{
        return '<a href="idioms/' + i.id + '/">' + i.zh + '</a>';
      }}).join('') + '</div>' : '');
    box.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
  }});
}})();
</script>"""
    return page("時間 × 列國 年表", body, current="timeline.html", canonical="timeline.html",
                desc="以時間為橫軸、列國為縱軸的春秋戰國二維年表；晉分三家、田氏代齊皆在圖上可見。")


def build_idioms_index(data):
    idioms = sorted(data["idioms"].values(), key=sort_key_idiom)

    def group_block(title, sub, items):
        cards = "".join(idiom_card(d, data) for d in items)
        return (f'<h2 class="section-title">{e(title)}'
                f'<span class="count">{len(items)} 條</span>'
                f'<span class="sub">{e(sub)}</span></h2>'
                f'<div class="grid">{cards}</div>')

    # 按分期
    by_period = ""
    for p in data["periods"]:
        items = [d for d in idioms if d.get("period") == p["id"]]
        if items:
            by_period += group_block(p["name"], f'前 {abs(p["start"])} – 前 {abs(p["end"])}', items)

    # 按文獻（以第一條典源為準）
    by_source = ""
    src_groups = {}
    for d in idioms:
        first = (d.get("dianyuan") or [{}])[0].get("source")
        src_groups.setdefault(first, []).append(d)
    for sid, items in sorted(src_groups.items(), key=lambda kv: -len(kv[1])):
        src = data["sources"].get(sid, {})
        by_source += group_block(f'《{src.get("name", sid)}》',
                                 src.get("locus_format", ""), items)

    # 按可信度
    by_rel = ""
    for r in ["信史", "大體可信", "孤證", "後世附會", "寓言"]:
        items = [d for d in idioms if d["reliability"] == r]
        if items:
            hint = {
                "信史": "同期或近期文獻互證，可繫年繫人",
                "大體可信": "主源可信，細節有後世增飾",
                "孤證": "僅一書所載，別無旁證",
                "後世附會": "晚出，或與早期文獻／出土材料相牴",
                "寓言": "諸子所設之譬喻，本無其事",
            }[r]
            by_rel += group_block(r, hint, items)

    # 按列國
    by_state = ""
    lane_states = sorted([s for s in data["states"].values() if s.get("lane")],
                         key=lambda s: s.get("lane_order", 99))
    for st in lane_states:
        items = [d for d in idioms if st["id"] in (d.get("states") or [])]
        if items:
            by_state += group_block(st["name"], st.get("note", "")[:60], items)

    body = f"""<main>
<div class="page-head">
  <h1>成語索引</h1>
  <p class="lede">同一批條目，四種切法。按分期看的是歷史脈絡，按文獻看的是史料分佈，
  按可信度看的是哪些可以當史實用、哪些只能當思想史材料用，按列國看的是地緣。</p>
</div>
<div class="filters" id="groupBar">
  <span class="label">分組方式</span>
  <button data-g="period" class="on">按分期</button>
  <button data-g="source">按文獻</button>
  <button data-g="rel">按可信度</button>
  <button data-g="state">按列國</button>
</div>
<div id="g-period">{by_period}</div>
<div id="g-source" hidden>{by_source}</div>
<div id="g-rel" hidden>{by_rel}</div>
<div id="g-state" hidden>{by_state}</div>
</main>
<script>
document.getElementById('groupBar').addEventListener('click', function (ev) {{
  var b = ev.target.closest('button'); if (!b) return;
  ['period', 'source', 'rel', 'state'].forEach(function (g) {{
    document.getElementById('g-' + g).hidden = (g !== b.dataset.g);
  }});
  [].forEach.call(this.querySelectorAll('button'), function (x) {{ x.classList.toggle('on', x === b); }});
}});
</script>"""
    return page("成語索引", body, current="idioms.html", canonical="idioms.html",
                desc="全部成語條目，可按分期、文獻、史料可信度、列國四種方式分組瀏覽。")


def build_events(data):
    ev_idioms = {}
    for d in data["idioms"].values():
        ev = (d.get("benshi") or {}).get("event")
        if ev:
            ev_idioms.setdefault(ev, []).append(d)

    out = ""
    for p in data["periods"]:
        evs = sorted([ev for ev in data["events"].values()
                      if p["start"] <= (year_num(ev.get("year")) or 0) <= p["end"]],
                     key=lambda x: year_num(x.get("year")) or 0)
        if not evs:
            continue
        rows = ""
        for ev in evs:
            yl = year_label(ev.get("year"))
            if ev.get("year_end"):
                yl += f" – {year_label(ev['year_end'])}"
            states = "".join(f'<span class="tag tag-state">{e(data["states"][s]["name"])}</span>'
                             for s in ev.get("states", []) if s in data["states"])
            ids = "".join(f'<a class="tag tag-type" href="idioms/{e(d["id"])}/">{e(d["idiom"]["zh"])}</a>'
                          for d in sorted(ev_idioms.get(ev["id"], []), key=sort_key_idiom))
            rows += f"""<div class="row">
  <span class="yr">{e(yl)}</span>
  <span class="main">
    <h3>{e(ev['name'])}</h3>
    <span class="sub">{rich(ev.get('significance', ''))}</span>
    <span class="tags"><span class="tag">{e(ev['type'])}</span>{rel_tag(ev['reliability'])}{states}{ids}</span>
  </span>
</div>"""
        out += (f'<h2 class="section-title">{e(p["name"])}'
                f'<span class="count">{len(evs)} 事</span>'
                f'<span class="sub">{e(p["marker"])}</span></h2>'
                f'<div class="rows">{rows}</div>')

    body = f"""<main>
<div class="page-head">
  <h1>編年大事</h1>
  <p class="lede">按分期排列的事件骨幹。每個事件下方列出繫於其上的成語——
  一個事件可以生出多條成語（城濮之戰生出退避三舍與表裡山河），
  一條成語也可能橫跨數十年（退避三舍的承諾與兌現相隔十九年）。</p>
</div>
{out}
</main>"""
    return page("編年大事", body, current="events.html", canonical="events.html",
                desc="春秋戰國編年大事表，按七個分期排列，每事列出所繫的成語。")


def build_people(data):
    lane_states = sorted([s for s in data["states"].values() if s.get("lane")],
                         key=lambda s: s.get("lane_order", 99))
    others = [s for s in data["states"].values() if not s.get("lane")]

    idiom_people = {}
    for d in data["idioms"].values():
        for pid in d.get("people") or []:
            idiom_people.setdefault(pid, []).append(d)

    def person_row(pr):
        yrs = f'{year_label(pr.get("birth")) if pr.get("birth") is not None else "？"} – ' \
              f'{year_label(pr.get("death")) if pr.get("death") is not None else "？"}'
        ids = "".join(f'<a class="tag tag-type" href="idioms/{e(d["id"])}/">{e(d["idiom"]["zh"])}</a>'
                      for d in sorted(idiom_people.get(pr["id"], []), key=sort_key_idiom))
        phil = ""
        if pr.get("philosophy_ref"):
            phil = (f'<a class="tag" href="https://cc-philosophy.vercel.app/philosophers/'
                    f'{e(pr["philosophy_ref"])}/" target="_blank" rel="noopener">哲學家知識庫 ↗</a>')
        return f"""<div class="row">
  <span class="yr">{e(yrs)}</span>
  <span class="main">
    <h3>{e(pr['name']['zh'])} <span style="font-size:13px;color:var(--muted);font-weight:400">{e(pr['name'].get('en',''))}</span></h3>
    <span class="sub">{e((pr.get('bio') or '')[:150])}…</span>
    <span class="tags"><span class="tag">{e(pr['role'])}</span>{ids}{phil}</span>
  </span>
</div>"""

    out = ""
    for st in lane_states + others:
        ppl = sorted([p for p in data["people"].values() if p["state"] == st["id"]],
                     key=lambda p: (year_num(p.get("birth")) if p.get("birth") is not None
                                    else year_num(p.get("sort_year")) or 0))
        if not ppl:
            continue
        out += (f'<h2 class="section-title">{e(st["name"])}'
                f'<span class="count">{len(ppl)} 人</span>'
                f'<span class="sub">{e((st.get("note") or "")[:70])}</span></h2>'
                f'<div class="rows">{"".join(person_row(p) for p in ppl)}</div>')

    body = f"""<main>
<div class="page-head">
  <h1>人物</h1>
  <p class="lede">按所屬列國分組，國內按生年排序。生卒不可考者以「？」標示。
  先秦思想家的思想部分不在本站重複撰寫，改以外連至<a href="https://cc-philosophy.vercel.app/" target="_blank" rel="noopener">哲學家知識庫</a>——
  那邊講他們想了什麼，這邊講他們身在什麼局裡。</p>
</div>
{out}
</main>"""
    return page("人物", body, current="people.html", canonical="people.html",
                desc="春秋戰國人物小傳，按列國分組；先秦思想家外連至哲學家知識庫。")


def build_sources(data):
    # 統計各書貢獻嘅成語數（以典源第一條為主源，其餘計入「亦見」）
    primary, secondary = {}, {}
    for d in data["idioms"].values():
        for i, c in enumerate(d.get("dianyuan") or []):
            sid = c.get("source")
            (primary if i == 0 else secondary).setdefault(sid, set()).add(d["id"])

    layer_names = {
        "A": ("編年骨幹", "時間軸的脊椎。《史記》兩張年表本身就是「年份 × 列國」的矩陣"),
        "B": ("敘事主源", "史事型成語的典源，絕大多數出於此四書"),
        "C": ("諸子", "寓言型成語的典源，亦保存大量不見於史書的掌故"),
        "D": ("出土文獻", "可信度與異說的現代依據——凡與傳世文獻相牴者必須並存互參"),
        "E": ("後世輯錄", "保存先秦材料，但已多所潤飾；孤證不可據"),
    }
    out = ""
    for layer in ["A", "B", "C", "D", "E"]:
        srcs = [s for s in data["sources"].values() if s.get("layer") == layer]
        if not srcs:
            continue
        srcs.sort(key=lambda s: -len(primary.get(s["id"], set())))
        cards = ""
        for s in srcs:
            n_p = len(primary.get(s["id"], set()))
            n_s = len(secondary.get(s["id"], set()))
            contrib = []
            if n_p:
                contrib.append(f"典源 {n_p} 條")
            if n_s:
                contrib.append(f"旁證 {n_s} 條")
            badge = (f'<span class="contrib">{"・".join(contrib)}</span>'
                     if contrib else '<span class="contrib" style="background:var(--surface-sunk);color:var(--muted)">本期未引</span>')
            link = ""
            if s.get("ctext"):
                link = (f'<a href="https://ctext.org/{e(s["ctext"])}/zh" target="_blank" '
                        f'rel="noopener" style="font-size:12.5px">ctext ↗</a>')
            meta = []
            if s.get("compiled") is not None:
                meta.append(f'成書約{year_label(s["compiled"])}')
            if s.get("compiler"):
                meta.append(e(s["compiler"]))
            if s.get("excavated"):
                meta.append(f'{s["excavated"]} 年出土')
            caveat = (f'<div class="caveat"><b>須注意：</b>{e(s["caveat"])}</div>'
                      if s.get("caveat") else "")
            cards += f"""<div class="src-card">
  <div class="top"><h3>《{e(s['name'])}》</h3>
    <span style="font-size:12.5px;color:var(--muted)">{e("・".join(meta))}</span>{link}{badge}</div>
  {f'<div class="nature">{e(s["nature"])}</div>' if s.get('nature') else ''}
  {caveat}
</div>"""
        title, sub = layer_names[layer]
        out += (f'<div class="src-layer"><h2 class="section-title">{layer}　{e(title)}'
                f'<span class="count">{len(srcs)} 部</span>'
                f'<span class="sub">{e(sub)}</span></h2>{cards}</div>')

    body = f"""<main>
<div class="page-head">
  <h1>文獻譜系</h1>
  <p class="lede">「春秋戰國的歷史該查哪些書」——這一頁就是答案，
  而且各書的「貢獻條數」是由本站數據自動統計出來的，不是寫死的。
  典源取最早：同一事若《左傳》與《史記》皆載，典源歸《左傳》，《史記》計為旁證。</p>
</div>
{out}
</main>"""
    return page("文獻譜系", body, current="sources.html", canonical="sources.html",
                desc="春秋戰國史料的四層譜系：編年骨幹、敘事主源、諸子、出土文獻，附各書貢獻成語數的自動統計。")


def build_idiom_page(d, data, prev_d, next_d):
    up = "../../"
    per = data["period_by_id"].get(d.get("period"), {})
    states = "".join(f'<span class="tag tag-state">{e(data["states"][s]["name"])}</span>'
                     for s in d.get("states", []) if s in data["states"])
    concepts = "".join(f'<span class="tag">{e(c)}</span>' for c in d.get("concepts") or [])

    layers = []

    # 第一層：本事
    benshi = d.get("benshi")
    if benshi:
        ev = data["events"].get(benshi.get("event"))
        ev_html = ""
        if ev:
            yl = year_label(ev.get("year"))
            if ev.get("year_end"):
                yl += f" – {year_label(ev['year_end'])}"
            ev_html = f"""<div style="margin-top:13px;padding-top:13px;border-top:1px solid var(--line)">
  <div style="font-size:12.5px;color:var(--muted);margin-bottom:5px">所繫事件</div>
  <div style="font-family:var(--serif);font-size:17px;color:var(--ink-strong)">{e(ev['name'])}
    <span style="font-family:var(--sans);font-size:13px;color:var(--muted)">（{e(yl)}）</span></div>
  <div style="font-size:14px;line-height:1.85;margin-top:6px">{rich(ev.get('narrative', ''))}</div>
  <div style="font-size:13.5px;color:var(--muted);margin-top:9px"><b>意義：</b>{rich(ev.get('significance', ''))}</div>
</div>"""
        layers.append(f"""<section class="layer">
  <h2><span class="num">第一層</span>本事<span class="hint">歷史上實際發生了什麼</span></h2>
  <p style="font-size:15px;line-height:1.9">{rich(benshi.get('summary'))}</p>
  {ev_html}
</section>""")
    else:
        layers.append(f"""<section class="layer">
  <h2><span class="num">第一層</span>本事<span class="hint">歷史上實際發生了什麼</span></h2>
  <p style="font-size:15px;line-height:1.9;color:var(--muted)">
  本條為<b>寓言型</b>（<code>type: parable</code>）——諸子所設之譬喻，並無史實本事。
  其史料價值不在記錄了什麼事，而在它顯示了那個時代的人如何論理。</p>
</section>""")

    # 第二層：典源
    quotes = "".join(quote_block(c, data) for c in d.get("dianyuan") or [])
    layers.append(f"""<section class="layer">
  <h2><span class="num">第二層</span>典源<span class="hint">最早見於哪本書、哪一段</span></h2>
  {quotes}
</section>""")

    # 第三層：語形定型
    cry = d.get("crystallisation")
    if cry:
        fa = (f'<div style="font-size:13px;color:var(--muted);margin-bottom:7px">'
              f'四字語形最早可考：<b style="color:var(--bronze-deep)">{e(cry["first_attested"])}</b></div>'
              if cry.get("first_attested") else "")
        moe = ""
        if cry.get("moe_id"):
            moe = (f'<div style="font-size:12.5px;color:var(--muted);margin-top:9px">'
                   f'交叉核對：<a href="https://dict.idioms.moe.edu.tw/idiomView.jsp?ID={e(cry["moe_id"])}'
                   f'&webMd=1&la=0" target="_blank" rel="noopener">教育部《成語典》 ↗</a></div>')
        layers.append(f"""<section class="layer">
  <h2><span class="num">第三層</span>語形定型<span class="hint">「四字成語」這個形式何時確立</span></h2>
  {fa}
  <p style="font-size:15px;line-height:1.9">{rich(cry.get('note'))}</p>
  {moe}
</section>""")

    # 第四層：可信度與異說
    variants = ""
    for v in d.get("variants") or []:
        src = data["sources"].get(v.get("source"), {})
        url = ctext_url(v.get("ctext_urn"))
        link = f' <a href="{e(url)}" target="_blank" rel="noopener">ctext ↗</a>' if url else ""
        variants += (f'<div class="variant">{rich(v.get("claim"))}'
                     f'<div class="src">——《{e(src.get("name", v.get("source")))}》'
                     f'{e(v.get("locus", ""))}{link}</div></div>')
    rel_hint = {
        "信史": "同期或近期文獻互證，可繫年、可繫人。",
        "大體可信": "主源可信，但細節有後世增飾。",
        "孤證": "僅一書所載，別無旁證，亦無反證。",
        "後世附會": "晚出，或與早期文獻、出土材料相牴。",
        "寓言": "諸子所設之譬喻，本無其事——但這不等於沒有價值：它是理解那個時代思想的一手材料。",
    }[d["reliability"]]
    layers.append(f"""<section class="layer">
  <h2><span class="num">第四層</span>可信度與異說<span class="hint">本事有多可信、有沒有相牴的記載</span></h2>
  <div style="display:flex;align-items:center;gap:11px;margin-bottom:11px">
    {rel_tag(d['reliability'])}<span style="font-size:13.5px;color:var(--muted)">{e(rel_hint)}</span>
  </div>
  {variants or '<p style="font-size:14px;color:var(--muted)">未見相牴之記載。</p>'}
</section>""")

    # 啟示
    les = d.get("lessons") or {}
    modern = ""
    if les.get("modern"):
        modern = f"""<div class="box modern">
  <h3>現代引申</h3><p>{rich(les['modern'])}</p>
  <div class="caveat">※ 引申義，非史料本身所有。</div>
</div>"""
    layers.append(f"""<section class="layer">
  <h2>啟示<span class="hint">史觀分析與現代引申分開處理</span></h2>
  <div class="lessons">
    <div class="box"><h3>史觀</h3><p>{rich(les.get('historical'))}</p></div>
    {modern}
  </div>
</section>""")

    # 關聯
    kind_label = {"same_event": "同一事件", "same_source": "同一典源",
                  "contrast": "意義相對", "derived": "由此衍生"}
    rel_html = ""
    for r in d.get("_related") or []:
        t = data["idioms"][r["target"]]
        rel_html += (f'<a href="{up}idioms/{e(t["id"])}/">{e(t["idiom"]["zh"])}'
                     f'<span class="kind">{e(kind_label.get(r["kind"], r["kind"]))}</span></a>')
    ppl_html = "".join(
        f'<a href="{up}people.html#{e(pid)}">{e(data["people"][pid]["name"]["zh"])}</a>'
        for pid in d.get("people") or [] if pid in data["people"]
    )
    layers.append(f"""<section class="layer">
  <h2>關聯</h2>
  {f'<div style="font-size:12.5px;color:var(--muted);margin-bottom:6px">相關成語</div><div class="rel-links" style="margin-bottom:14px">{rel_html}</div>' if rel_html else ''}
  <div style="font-size:12.5px;color:var(--muted);margin-bottom:6px">相關人物</div>
  <div class="rel-links">{ppl_html}</div>
</section>""")

    refs = "".join(f'<li><a href="{e(u)}" target="_blank" rel="noopener">{e(u)}</a></li>'
                   for u in d.get("references") or [])
    notes = (f'<section class="layer"><h2>附註</h2>'
             f'<p style="font-size:14px;line-height:1.85">{rich(d.get("notes"))}</p></section>'
             if d.get("notes") else "")

    essay = markdown(d["_md"])

    prevnext = '<div class="prevnext">'
    prevnext += (f'<a href="{up}idioms/{e(prev_d["id"])}/">← {e(prev_d["idiom"]["zh"])}</a>'
                 if prev_d else "<span></span>")
    prevnext += (f'<a href="{up}idioms/{e(next_d["id"])}/">{e(next_d["idiom"]["zh"])} →</a>'
                 if next_d else "<span></span>")
    prevnext += "</div>"

    jyut = f'・粵 {e(d["idiom"]["jyutping"])}' if d["idiom"].get("jyutping") else ""
    body = f"""<main class="narrow">
<div class="idiom-hero">
  <h1>{e(d['idiom']['zh'])}</h1>
  <div class="romanisation">{e(d['idiom']['pinyin'])}{jyut}</div>
  <div class="literal"><b>字面</b>　{e(d['idiom']['literal'])}　·　{e(d['idiom']['en'])}</div>
  <div class="meaning">{e(d.get('meaning'))}</div>
  <div class="tags">
    {type_tag(d['type'])}{rel_tag(d['reliability'])}
    <span class="tag">{e(per.get('name', ''))}</span>
    <span class="tag">{e(year_label(d.get('year')))}{('・' + e(d['year_note'])) if d.get('year_note') else ''}</span>
    {states}{concepts}
  </div>
</div>
{''.join(layers)}
<section class="layer"><h2>論述</h2><div class="essay">{essay}</div></section>
{notes}
<section class="layer"><h2>撰寫依據</h2><ul style="margin-left:1.3em;font-size:13.5px">{refs}</ul></section>
{prevnext}
</main>"""
    return page(d["idiom"]["zh"], body, current="idioms.html", depth=2,
                canonical=f"idioms/{d['id']}/",
                desc=f"{d['idiom']['zh']}——{d.get('meaning')} 本事、典源、語形定型與史料可信度四層考據。")


# ────────────────────────── 搜尋索引 ──────────────────────────

def build_search_index(data):
    rows = []
    for d in sorted(data["idioms"].values(), key=sort_key_idiom):
        per = data["period_by_id"].get(d.get("period"), {})
        rows.append({
            "t": d["idiom"]["zh"], "c": "成語", "u": f"idioms/{d['id']}/",
            "s": f"{year_label(d.get('year'))}・{per.get('name','')}",
            "k": " ".join([d["idiom"]["zh"], d["idiom"]["pinyin"], d["idiom"].get("jyutping", ""),
                           d.get("meaning", ""), " ".join(d.get("concepts") or [])]),
        })
    for ev in sorted(data["events"].values(), key=lambda x: year_num(x.get("year")) or 0):
        rows.append({
            "t": ev["name"], "c": "事件", "u": "events.html",
            "s": year_label(ev.get("year")),
            "k": " ".join([ev["name"], ev.get("significance", "")]),
        })
    for pr in data["people"].values():
        rows.append({
            "t": pr["name"]["zh"], "c": "人物", "u": f"people.html#{pr['id']}",
            "s": f'{data["states"].get(pr["state"], {}).get("name", "")}・{pr["role"]}',
            "k": " ".join([pr["name"]["zh"], pr["name"].get("en", ""),
                           pr["name"].get("personal", "") or "", (pr.get("bio") or "")[:80]]),
        })
    for s in data["sources"].values():
        rows.append({
            "t": f'《{s["name"]}》', "c": "文獻", "u": "sources.html",
            "s": s.get("compiler", "") or "",
            "k": " ".join([s["name"], s.get("full_name", "") or "", s.get("nature", "") or ""]),
        })
    return "var SEARCH_INDEX = " + json.dumps(rows, ensure_ascii=False) + ";\n"


# ────────────────────────── 主流程 ──────────────────────────

def main():
    data = load_all()
    PERIOD_END.update({p["id"]: p["end"] for p in data["periods"]})

    # 自動生成反向關聯
    for d in data["idioms"].values():
        d["_related"] = list(d.get("related_idioms") or [])
    for d in data["idioms"].values():
        for r in d.get("related_idioms") or []:
            target = data["idioms"].get(r["target"])
            if target is None:
                continue
            if not any(x["target"] == d["id"] for x in target["_related"]):
                target["_related"].append({"target": d["id"], "kind": r["kind"],
                                           "note": r.get("note", "")})

    counts = {"n_idioms": len(data["idioms"]),
              "n_events": len(data["events"]),
              "n_people": len(data["people"])}
    # 用專用標記而唔用 str.format——生成嘅 HTML 內含大量 JS 大括號
    tokens = {"@@N_IDIOMS@@": str(counts["n_idioms"]),
              "@@N_EVENTS@@": str(counts["n_events"]),
              "@@N_PEOPLE@@": str(counts["n_people"])}

    def write(rel_path, content):
        for k, v in tokens.items():
            content = content.replace(k, v)
        p = ROOT / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    write("index.html", build_index(data))
    write("timeline.html", build_timeline(data))
    write("idioms.html", build_idioms_index(data))
    write("events.html", build_events(data))
    write("people.html", build_people(data))
    write("sources.html", build_sources(data))
    write("assets/search-index.js", build_search_index(data))

    ordered = sorted(data["idioms"].values(), key=sort_key_idiom)
    for i, d in enumerate(ordered):
        prev_d = ordered[i - 1] if i > 0 else None
        next_d = ordered[i + 1] if i < len(ordered) - 1 else None
        write(f"idioms/{d['id']}/index.html", build_idiom_page(d, data, prev_d, next_d))

    # 404 / robots / sitemap / .nojekyll
    write("404.html", page("找不到頁面", """<main class="narrow">
<div class="page-head"><h1>找不到這一頁</h1>
<p class="lede">網址可能已經變更，或者這一條還沒收錄。
可以回<a href="index.html">總覽</a>看看，或者按 <kbd>/</kbd> 全站搜尋。</p></div></main>"""))
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    today = date.today().isoformat()
    urls = ["", "timeline.html", "idioms.html", "events.html", "people.html", "sources.html"]
    urls += [f"idioms/{d['id']}/" for d in ordered]
    sm = "\n".join(
        f"  <url><loc>{SITE_URL}/{u}</loc><lastmod>{today}</lastmod></url>" for u in urls)
    write("sitemap.xml",
          f'<?xml version="1.0" encoding="UTF-8"?>\n'
          f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{sm}\n</urlset>\n')
    (ROOT / ".nojekyll").touch()

    print(f"生成完成：{counts['n_idioms']} 條成語詳頁 + 6 個索引頁"
          f"（事件 {counts['n_events']}、人物 {counts['n_people']}）")


if __name__ == "__main__":
    main()
