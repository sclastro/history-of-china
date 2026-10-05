#!/usr/bin/env python3
"""由 idioms / events / people / data 生成全站靜態 HTML。

生成：
    index.html      總覽格陣（全部成語，可篩選）
    timeline.html   時間 × 列國 二維年表（可按分期放大；手機退化為按分期收合的列表）
    idioms.html     成語索引（可按分期／文獻／可信度／列國切換分組，可即時篩選）
    events.html     編年大事索引（按分期，可按類型、列國篩選）
    people.html     人物索引（按國分組，可按身分篩選）
    sources.html    文獻譜系（含各書貢獻成語數，由數據自動統計）
    idioms/<id>/index.html   成語詳頁（四層考據 + 論述文章）
    event/<id>/index.html    事件頁（敘事、原文選段、所繫成語、相關人物）
    person/<id>/index.html   人物頁（小傳、生平、相關成語、事件與人物、附註）
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
SITE_URL = "https://cc-history-of-china.vercel.app"
REPO_URL = "https://github.com/sclastro/history-of-china"
REPO_BRANCH = "claude/spring-autumn-history-site-f4tzkd"
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
    return tidy_all(data)


# ────────────────────────── 小工具 ──────────────────────────

BOLD = re.compile(r"\*\*([^*]+)\*\*")

# YAML 折疊純量同 Markdown 段落換行都會摺成空格；中文之間唔應該有空格，
# 故一律把「中日韓字元之間嘅空白」刪走（拉丁字母、數字之間嘅空格保留）。
CJK = r"\u2e80-\u9fff\uf900-\ufaff\uff01-\uff60\u3000-\u303f\u2014\u2026\u2018\u2019\u201c\u201d"
CJK_SPACE = re.compile(rf"(?<=[{CJK}])[ \t]+(?=[{CJK}])")


# 粗體標記 ** 夾喺中間時，空白亦要一併清走
CJK_SPACE_BOLD = re.compile(rf"(?<=[{CJK}])[ \t]+(?=\*\*[{CJK}])")
CJK_SPACE_BOLD2 = re.compile(rf"(?<=[{CJK}])\*\*[ \t]+(?=[{CJK}])")


def cjk_tidy(text):
    text = CJK_SPACE.sub("", text)
    text = CJK_SPACE_BOLD.sub("", text)
    return CJK_SPACE_BOLD2.sub("**", text)


def tidy_all(node):
    """遞迴清走資料中所有字串的中文字間空白。"""
    if isinstance(node, str):
        return cjk_tidy(node)
    if isinstance(node, list):
        return [tidy_all(x) for x in node]
    if isinstance(node, dict):
        return {k: tidy_all(v) for k, v in node.items()}
    return node


def e(text):
    return html.escape(str(text if text is not None else ""))


# 敘事、小傳中緊隨文言引語嘅行內白話，寫作：「文言」（白話：……）
# 呈現時**倒轉主次**——白話入正文，文言縮細做參考。讀者主要睇白話。
QUOTE_GLOSS = re.compile(
    r"(「[^「」]*(?:『[^』]*』[^「」]*)*」)\s*（白話：([^）]+)）")
GLOSS = re.compile(r"（白話：([^）]+)）")


def rich(text):
    """容許 **粗體** 同「文言」（白話：…）；後者渲染為白話在前、原文在後。"""
    out = BOLD.sub(r"<strong>\1</strong>", e(text))
    out = QUOTE_GLOSS.sub(
        r'<span class="vern">\2</span>'
        r'<span class="orig">（原文：\1）</span>', out)
    # 未緊接引語嘅白話（罕見）仍照舊呈現
    return GLOSS.sub(r'<span class="vern">\1</span>', out)


def paras(text):
    """多段敘事：資料中的換行即分段，每段各成 <p>。"""
    return "".join(f"<p>{rich(x.strip())}</p>" for x in (text or "").split("\n") if x.strip())


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
            text = cjk_tidy(" ".join(para))
            # 緊接文言引文之後嘅白話段，寫作「白話：……」
            if text.startswith("白話："):
                out.append('<p class="vernacular"><span class="vlabel">白話</span>'
                           f'{inline(text[3:].strip())}</p>')
            else:
                out.append(f"<p>{inline(text)}</p>")
            para = []
        if quote:
            body = f"<p>{inline(cjk_tidy(' '.join(quote)))}</p>"
            out.append(f"<blockquote>{body}</blockquote>")
            quote = []
        if ul:
            body = "".join(f"<li>{inline(cjk_tidy(x))}</li>" for x in ul)
            out.append(f"<ul>{body}</ul>")
            ul = []
        if ol:
            body = "".join(f"<li>{inline(cjk_tidy(x))}</li>" for x in ol)
            out.append(f"<ol>{body}</ol>")
            ol = []

    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            flush()
        elif ln.startswith("#"):
            flush()
            level = len(ln) - len(ln.lstrip("#"))
            out.append(f"<h{level}>{inline(cjk_tidy(ln[level:].strip()))}</h{level}>")
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
    return pair_quote_vernacular(out)


BQ_RE = re.compile(r"^<blockquote>(.*)</blockquote>$", re.S)
VERN_RE = re.compile(
    r'^<p class="vernacular"><span class="vlabel">白話</span>(.*)</p>$', re.S)


def pair_quote_vernacular(blocks):
    """把「文言引文 + 緊隨的白話段」重排為白話在前、原文在後（可摺疊）。"""
    out, i = [], 0
    while i < len(blocks):
        bq = BQ_RE.match(blocks[i])
        vn = VERN_RE.match(blocks[i + 1]) if bq and i + 1 < len(blocks) else None
        if bq and vn:
            out.append(
                f'<div class="passage"><p class="passage-vern">{vn.group(1)}</p>'
                f'<details class="passage-orig" open><summary>原文</summary>'
                f'<blockquote>{bq.group(1)}</blockquote></details></div>')
            i += 2
        else:
            out.append(blocks[i])
            i += 1
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


# 模板內段落文字換行：中文字之間、中文字與行內標籤之間的換行會顯示成空格，輸出前刪去
INLINE_NL = re.compile(rf"(?<=[{CJK}])[ \t]*\n[ \t]*(?=[{CJK}]|</?(?:b|a|span|em|strong)\b)"
                       rf"|(?<=</b>|</a>)[ \t]*\n[ \t]*(?=[{CJK}])")


def page(title, body, *, current="", depth=0, desc=None, canonical=""):
    body = INLINE_NL.sub("", body)
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
  <a href="{REPO_URL}/blob/{REPO_BRANCH}/docs/design.md" target="_blank" rel="noopener">四層考據原則</a>
  <a href="{REPO_URL}/blob/{REPO_BRANCH}/docs/sources.md" target="_blank" rel="noopener">引用規範</a>
  <a href="{REPO_URL}/blob/{REPO_BRANCH}/docs/framework.md" target="_blank" rel="noopener">收錄骨架</a>
  <a href="{REPO_URL}" target="_blank" rel="noopener">原始碼與資料</a>
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
    // 標題完全相符者排最前，其次標題開首相符、標題包含，最後才是其他欄位相符
    function rank(r) {{ var t = r.t.toLowerCase().replace(/[《》]/g, '');
      return t === q ? 0 : t.indexOf(q) === 0 ? 1 : t.indexOf(q) >= 0 ? 2 : 3; }}
    shown = q ? SEARCH_INDEX.filter(function (r) {{ return r.k.toLowerCase().indexOf(q) >= 0; }})
                  .map(function (r, i) {{ return [rank(r), i, r]; }})
                  .sort(function (a, b) {{ return a[0] - b[0] || a[1] - b[1]; }})
                  .map(function (x) {{ return x[2]; }}).slice(0, 40)
              : SEARCH_INDEX.slice(0, 20);
    sel = 0;
    if (!shown.length) {{ results.innerHTML = '<div class="cmdk-empty">找不到相符的條目。</div>'; return; }}
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
// 粵語發音：全站共用一個 audio 物件，不必每條成語各開一個
(function () {{
  var a = null;
  document.addEventListener('click', function (ev) {{
    var b = ev.target.closest ? ev.target.closest('.say') : null;
    if (!b) return;
    ev.preventDefault();
    if (!a) a = new Audio();
    if (!a.paused) {{ a.pause(); a.currentTime = 0; }}
    document.querySelectorAll('.say.playing').forEach(function (x) {{
      x.classList.remove('playing');
    }});
    a.src = b.getAttribute('data-a');
    b.classList.add('playing');
    a.onended = a.onerror = function () {{ b.classList.remove('playing'); }};
    a.play().catch(function () {{ b.classList.remove('playing'); }});
  }});
}})();
</script>
</body>
</html>
"""


SPEAKER_SVG = (
    '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
    '<path d="M4 9v6h4l5 4V5L8 9H4z"/>'
    '<path class="w1" d="M16.5 8.5a5 5 0 0 1 0 7"/>'
    '<path class="w2" d="M19 6a8.5 8.5 0 0 1 0 12"/></svg>'
)


def say_button(iid, up="", label="", cls=""):
    """粵語發音掣。音檔喺建置時預先生成，瀏覽器只負責播放。"""
    aria = f"讀出「{label}」的粵語發音" if label else "讀出粵語發音"
    return (f'<button type="button" class="say {cls}" data-a="{up}assets/audio/{e(iid)}.mp3"'
            f' aria-label="{e(aria)}" title="粵語發音">{SPEAKER_SVG}</button>')


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
    # 掣要放喺 <a> 外面——<button> 唔可以嵌喺 <a> 入面（無效 HTML）
    return f"""<div class="card-wrap">{say_button(d['id'], up, d['idiom']['zh'], "card-say")}
<a class="card" href="{up}idioms/{e(d['id'])}/">
  <span class="zh">{e(d['idiom']['zh'])}</span>
  <span class="meta">{e(year_label(d.get('year')))}・{e(per.get('name', ''))}</span>
  <span class="meaning">{e(d.get('meaning'))}</span>
  <span class="tags">{type_tag(d['type'])}{'' if d['reliability'] == '寓言' else rel_tag(d['reliability'])}{states}</span>
</a></div>"""


def cite_line(c, data):
    src = data["sources"].get(c.get("source"), {})
    url = ctext_url(c.get("ctext_urn"))
    book = f'<span class="book">《{e(src.get("name", c.get("source")))}》</span>'
    locus = e(c.get("locus", ""))
    link = f' <a href="{e(url)}" target="_blank" rel="noopener">ctext ↗</a>' if url else ""
    return f"{book}<span>{locus}</span>{link}"


def quote_block(c, data):
    """白話在上（主），文言原文在下（參考，可摺疊）。"""
    parts = [f'<div class="cite">{cite_line(c, data)}</div>']
    if c.get("translation"):
        parts.append(f'<div class="translation">{e(c["translation"])}</div>')
    parts.append('<details class="orig-wrap" open><summary>原文</summary>'
                 f'<div class="original">{e(c.get("quote", ""))}</div></details>')
    if c.get("note"):
        parts.append(f'<div class="note">{e(c["note"])}</div>')
    return f'<div class="quote-block">{"".join(parts)}</div>'



def event_original_blocks(ev, data):
    """事件的原文選段：每段白話在上、原文在下。"""
    items = ev.get("original") or []
    if not items:
        return ""
    base = (ev.get("sources") or [{}])[0]
    blocks = ""
    for c in items:
        c = {"source": base.get("source"), **c}
        if "ctext_urn" not in c:
            # 沿用 sources 中同書同篇者的連結（不限第一條）
            same = [s for s in ev.get("sources") or []
                    if s.get("source") == c["source"] and s.get("locus") == c.get("locus")]
            if same and same[0].get("ctext_urn"):
                c["ctext_urn"] = same[0]["ctext_urn"]
        speaker = f'<span class="speaker">{e(c["speaker"])}</span>・' if c.get("speaker") else ""
        blocks += (f'<div class="quote-block"><div class="cite">{speaker}{cite_line(c, data)}</div>'
                   f'<div class="translation">{e(c.get("translation", ""))}</div>'
                   f'<details class="orig-wrap" open><summary>原文</summary>'
                   f'<div class="original">{e(c.get("quote", ""))}</div></details></div>')
    return blocks


def event_originals(ev, data):
    """成語頁內的事件原文選段：整組預設摺疊。"""
    n = len(ev.get("original") or [])
    if not n:
        return ""
    return (f'<details class="ev-original"><summary>原文選段・白話對照（{n} 段）</summary>'
            f'{event_original_blocks(ev, data)}</details>')

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
  <p class="lede">以四字成語為主軸，重新組織春秋戰國五百五十年的歷史事件、人物與概念。
  每條成語都分清<b>本事</b>（實際發生了甚麼）、<b>典源</b>（最早見於哪一段）、
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


# ────────────────────────── 索引頁共用：篩選欄、分組跳轉 ──────────────────────────

def ev_url(eid, up=""):
    return f"{up}event/{eid}/"


def person_url(pid, up=""):
    return f"{up}person/{pid}/"


def ev_year_label(ev):
    yl = year_label(ev.get("year"))
    if ev.get("year_end"):
        yl += f" – {year_label(ev['year_end'])}"
    return yl


def person_years(pr):
    b = year_label(pr["birth"]) if pr.get("birth") is not None else "？"
    d = year_label(pr["death"]) if pr.get("death") is not None else "？"
    return f"{b} – {d}"


def event_idioms(data):
    out = {}
    for d in data["idioms"].values():
        ev = (d.get("benshi") or {}).get("event")
        if ev:
            out.setdefault(ev, []).append(d)
    for v in out.values():
        v.sort(key=sort_key_idiom)
    return out


def person_idioms(data):
    out = {}
    for d in data["idioms"].values():
        for pid in d.get("people") or []:
            out.setdefault(pid, []).append(d)
    for v in out.values():
        v.sort(key=sort_key_idiom)
    return out


def person_events(data):
    out = {}
    for ev in data["events"].values():
        for pid in ev.get("people") or []:
            out.setdefault(pid, []).append(ev)
    for v in out.values():
        v.sort(key=lambda x: year_num(x.get("year")) or 0)
    return out


def ordered_people(data):
    """人物總次序：按年表泳道的列國次序，國內按生年（不可考者用 sort_year）。"""
    lane = sorted([s for s in data["states"].values() if s.get("lane")],
                  key=lambda s: s.get("lane_order", 99))
    others = [s for s in data["states"].values() if not s.get("lane")]
    groups = []
    for st in lane + others:
        ppl = sorted([p for p in data["people"].values() if p["state"] == st["id"]],
                     key=lambda p: (year_num(p.get("birth")) if p.get("birth") is not None
                                    else year_num(p.get("sort_year")) or 0))
        if ppl:
            groups.append((st, ppl))
    return groups


def ordered_events(data):
    return sorted(data["events"].values(),
                  key=lambda x: (year_num(x.get("year")) or 0, x["id"]))


def jump_nav(items, group=None, hidden=False):
    """分組跳轉列：items 為 (錨點, 標籤, 數目)。"""
    attr = f' data-g="{group}"' if group else ""
    attr += " hidden" if hidden else ""
    links = "".join(f'<a href="#{e(a)}">{e(label)}<span class="n">{n}</span></a>'
                    for a, label, n in items)
    return f'<nav class="idx-jump" aria-label="跳至分組"{attr}>{links}</nav>'


def idx_toolbar(navs, placeholder, controls=""):
    return f"""<div class="idx-bar" id="idxBar">
  <div class="idx-row">
    <input type="search" id="idxQ" class="idx-q" placeholder="{e(placeholder)}" autocomplete="off" aria-label="篩選">
    {controls}
    <span class="idx-count" id="idxCount"></span>
  </div>
  {navs}
</div>"""


def idx_select(field, label, options):
    opts = "".join(f'<option value="{e(v)}">{e(t)}</option>' for v, t in options)
    return (f'<select class="idx-sel" data-f="{field}" aria-label="{e(label)}">'
            f'<option value="">{e(label)}：全部</option>{opts}</select>')


ON_CLS = ' class="on"'

# 篩選、跳轉、分組切換的共用腳本（純 JS 字串，不經 f-string）
INDEX_JS = """<script>
(function () {
  var root = document.documentElement, bar = document.getElementById('idxBar');
  var q = document.getElementById('idxQ'), count = document.getElementById('idxCount');
  var sels = [].slice.call(document.querySelectorAll('.idx-sel'));
  var items = [].slice.call(document.querySelectorAll('.idx-item'));
  var secs = [].slice.call(document.querySelectorAll('.idx-sec'));
  function setVars() {
    var h = document.querySelector('.site-header');
    var sticky = h && getComputedStyle(h).position === 'sticky';
    root.style.setProperty('--hdr', (sticky ? h.offsetHeight : 0) + 'px');
    root.style.setProperty('--bar', bar.offsetHeight + 'px');
  }
  function scope() { return document.querySelector('[data-idx-scope]:not([hidden])') || document; }
  function apply() {
    var t = q.value.trim().toLowerCase(), filtered = !!t;
    sels.forEach(function (s) { if (s.value) filtered = true; });
    items.forEach(function (it) {
      var ok = !t || it.getAttribute('data-k').toLowerCase().indexOf(t) >= 0;
      sels.forEach(function (s) {
        if (s.value && (' ' + (it.getAttribute('data-' + s.dataset.f) || '') + ' ').indexOf(' ' + s.value + ' ') < 0) ok = false;
      });
      it.hidden = !ok;
    });
    secs.forEach(function (s) {
      var n = s.querySelectorAll('.idx-item:not([hidden])').length;
      s.hidden = !n;
      [].forEach.call(document.querySelectorAll('.idx-jump a[href="#' + s.id + '"]'), function (a) {
        a.classList.toggle('empty', !n); a.querySelector('.n').textContent = n;
      });
    });
    // 同一條目可在多個分組出現（如按列國），以 data-id 去重計數
    function uniq(list) {
      var s = {}, n = 0;
      [].forEach.call(list, function (x) { var k = x.getAttribute('data-id') || Math.random(); if (!s[k]) { s[k] = 1; n++; } });
      return n;
    }
    var sc = scope(), vis = uniq(sc.querySelectorAll('.idx-item:not([hidden])')),
        tot = uniq(sc.querySelectorAll('.idx-item'));
    count.textContent = filtered ? '顯示 ' + vis + ' / ' + tot : '共 ' + tot + ' 項';
    var empty = document.getElementById('idxEmpty');
    if (empty) empty.hidden = vis > 0;
    spy();
  }
  // 捲動時標示目前所在分組
  var ticking = false;
  function spy() {
    var off = bar.getBoundingClientRect().bottom + 24;
    var cur = null;
    secs.forEach(function (s) {
      if (!s.hidden && s.offsetParent !== null && s.getBoundingClientRect().top <= off) cur = s.id;
    });
    [].forEach.call(document.querySelectorAll('.idx-jump:not([hidden]) a'), function (a) {
      var on = a.getAttribute('href') === '#' + cur;
      if (on && !a.classList.contains('on')) {
        var nav = a.parentNode;
        nav.scrollLeft = a.offsetLeft - nav.clientWidth / 2 + a.offsetWidth / 2;
      }
      a.classList.toggle('on', on);
    });
    ticking = false;
  }
  window.addEventListener('scroll', function () {
    if (!ticking) { ticking = true; requestAnimationFrame(spy); }
  }, { passive: true });
  window.addEventListener('resize', setVars);
  q.addEventListener('input', apply);
  sels.forEach(function (s) { s.addEventListener('change', apply); });
  // 成語索引：切換分組方式
  var groups = document.getElementById('idxGroups');
  if (groups) groups.addEventListener('click', function (ev) {
    var b = ev.target.closest('button'); if (!b) return;
    var g = b.dataset.g;
    [].forEach.call(groups.querySelectorAll('button'), function (x) {
      x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', x === b);
    });
    [].forEach.call(document.querySelectorAll('[data-idx-scope]'), function (c) { c.hidden = c.id !== 'g-' + g; });
    [].forEach.call(document.querySelectorAll('.idx-jump[data-g]'), function (n) { n.hidden = n.dataset.g !== g; });
    try { localStorage.setItem('idiomGroup', g); } catch (e) {}
    setVars(); apply();
  });
  if (groups) {
    var saved = null;
    try { saved = localStorage.getItem('idiomGroup'); } catch (e) {}
    var btn = saved && groups.querySelector('button[data-g="' + saved + '"]');
    if (btn) btn.click();
  }
  setVars(); apply();
})();
</script>"""


# ────────────────────────── 年表 ──────────────────────────

def build_timeline(data):
    span = TL_END - TL_START

    def pct(y):
        return max(0, min(100, (y - TL_START) / span * 100))

    ev_idioms = event_idioms(data)

    # 無 JS 時的預設位置（全覽）；有 JS 時由腳本按縮放範圍重排
    ticks = "".join(
        f'<span class="tick" style="left:{pct(y):.3f}%">前 {abs(y)}</span>'
        for y in range(-750, -200, 50)
    )
    segs = ""
    for p in data["periods"]:
        left = pct(p["start"])
        width = pct(p["end"]) - left
        segs += (f'<button type="button" class="seg" data-p="{e(p["id"])}" '
                 f'style="left:{left:.3f}%;width:{width:.3f}%" '
                 f'title="放大：{e(p["name"])}">{e(p["name"].split("・")[0])}</button>')

    lanes = ""
    lane_states = sorted([s for s in data["states"].values() if s.get("lane")],
                         key=lambda s: s.get("lane_order", 99))
    for st in lane_states:
        founded = max(st.get("founded") or TL_START, TL_START)
        ended = min(st.get("ended") or TL_END, TL_END)
        a, b = pct(founded), pct(ended)
        cls = "span succ" if st.get("successor_of") else "span"
        dots = ""
        for ev in ordered_events(data):
            if st["id"] not in (ev.get("states") or []):
                continue
            n = year_num(ev.get("year"))
            if n is None:
                continue
            dots += (f'<button type="button" class="tl-dot" data-ev="{e(ev["id"])}" data-y="{n}" '
                     f'data-type="{e(ev["type"])}" style="left:{pct(n):.3f}%" '
                     f'title="{e(year_label(n))}　{e(ev["name"])}" aria-label="{e(ev["name"])}"></button>')
        lanes += (f'<div class="tl-lane" data-a="{founded}" data-b="{ended}">'
                  f'<span class="name">{e(st["name"])}</span>'
                  f'<span class="{cls}" style="left:{a:.3f}%;width:{max(b - a, 0.4):.3f}%"></span>'
                  f'{dots}</div>')

    ev_json = {}
    for ev in data["events"].values():
        ev_json[ev["id"]] = {
            "name": ev["name"],
            "y": year_num(ev.get("year")),
            "yr": ev_year_label(ev),
            "type": ev["type"],
            "rel": ev["reliability"],
            "states": [data["states"][s]["name"] for s in ev.get("states", []) if s in data["states"]],
            "sig": rich(ev.get("significance", "")),
            "idioms": [{"zh": d["idiom"]["zh"], "id": d["id"]} for d in ev_idioms.get(ev["id"], [])],
        }

    # 圓點以外的另一入口：當前範圍內的事件清單
    ev_list = "".join(
        f'<button type="button" class="tl-ev" data-ev="{e(ev["id"])}" data-y="{year_num(ev.get("year")) or 0}">'
        f'<span class="y">{e(year_label(ev.get("year")))}</span>{e(ev["name"])}</button>'
        for ev in ordered_events(data)
    )

    zoom = ('<button type="button" data-p="" class="on" aria-pressed="true">全覽</button>' + "".join(
        f'<button type="button" data-p="{e(p["id"])}" aria-pressed="false" title="{e(p["name"])}">'
        f'{e(p["name"].split("・")[0])}</button>'
        for p in data["periods"]))
    periods_json = {p["id"]: [p["start"], p["end"], p["name"]] for p in data["periods"]}

    # 手機版：按分期收合，每事連到事件頁
    mobile = ""
    for p in data["periods"]:
        evs = [ev for ev in ordered_events(data)
               if p["start"] <= (year_num(ev.get("year")) or 0) <= p["end"]]
        if not evs:
            continue
        rows = ""
        for ev in evs:
            ids = "".join(
                f'<a href="idioms/{e(d["id"])}/">{e(d["idiom"]["zh"])}</a>'
                for d in ev_idioms.get(ev["id"], [])
            )
            rows += (f'<div class="tlm-row"><span class="yr">{e(year_label(ev.get("year")))}</span>'
                     f'<span class="main"><a class="t" href="{ev_url(ev["id"])}">{e(ev["name"])}</a>'
                     f'<span class="tags">{ids}</span></span></div>')
        mobile += (f'<details><summary>{e(p["name"])}'
                   f'<span class="yr">前 {abs(p["start"])} – 前 {abs(p["end"])}・{len(evs)} 事</span></summary>'
                   f'<div class="body">{rows}</div></details>')

    body = f"""<main>
<div class="page-head">
  <h1>時間 × 列國</h1>
  <p class="lede">橫軸為時間，縱軸為列國。晉在前 403 年分為趙、魏、韓，齊在前 386 年由田氏取代姜姓（綠色泳道）。
  圓點太密時，可先選一個分期放大；圖下另列該段全部事件，點選即顯示說明。</p>
</div>
<div class="filters tl-zoom" id="tlZoom"><span class="label">範圍</span>{zoom}</div>
<div class="timeline-wrap"><div class="timeline" id="tl">
  <div class="tl-periods">{segs}</div>
  <div class="tl-axis">{ticks}</div>
  {lanes}
</div></div>
<div class="tl-legend"><span><i data-type="戰役"></i>戰役</span><span><i data-type="會盟"></i>會盟・外交</span>
  <span><i data-type="變法"></i>變法</span><span><i></i>其他</span></div>
<div class="tl-evs" id="tlEvs">{ev_list}</div>
<div class="tl-detail" id="tlDetail"><span class="placeholder">點選圓點或上方事件，這裡會顯示事件說明與相關成語。</span></div>
<div class="tl-mobile">{mobile}</div>
</main>
<script>
var EVENTS = {json.dumps(ev_json, ensure_ascii=False)};
var PERIODS = {json.dumps(periods_json, ensure_ascii=False)};
var TL_FULL = [{TL_START}, {TL_END}];
</script>
<script>
(function () {{
  var tl = document.getElementById('tl'), box = document.getElementById('tlDetail');
  var zoom = document.getElementById('tlZoom'), evs = document.getElementById('tlEvs');
  var range = TL_FULL.slice(), selId = null;
  var GAP = 20, ROW = 18;
  function pct(y) {{ return (y - range[0]) / (range[1] - range[0]) * 100; }}
  function step(span) {{ return span > 300 ? 50 : span > 140 ? 20 : span > 60 ? 10 : 5; }}
  function layout() {{
    var lo = range[0], hi = range[1], st = step(hi - lo), html = '';
    for (var y = Math.ceil(lo / st) * st; y <= hi; y += st)
      if (pct(y) <= 97) html += '<span class="tick" style="left:' + pct(y) + '%">前 ' + Math.abs(y) + '</span>';
    tl.querySelector('.tl-axis').innerHTML = html;
    [].forEach.call(tl.querySelectorAll('.tl-periods .seg'), function (s) {{
      var p = PERIODS[s.dataset.p], a = Math.max(p[0], lo), b = Math.min(p[1], hi);
      s.hidden = b <= a;
      s.style.left = pct(a) + '%'; s.style.width = (pct(b) - pct(a)) + '%';
      s.textContent = (pct(b) - pct(a) > 12 ? p[2] : p[2].split('・')[0]);
    }});
    var width = tl.querySelector('.tl-axis').clientWidth;
    [].forEach.call(tl.querySelectorAll('.tl-lane'), function (lane) {{
      var a = Math.max(+lane.dataset.a, lo), b = Math.min(+lane.dataset.b, hi);
      lane.hidden = b <= a;
      var sp = lane.querySelector('.span');
      sp.style.left = pct(a) + '%'; sp.style.width = Math.max(pct(b) - pct(a), .4) + '%';
      // 圓點相距太近時改排到下一行，免得重疊
      var rows = [];
      [].forEach.call(lane.querySelectorAll('.tl-dot'), function (d) {{
        var y = +d.dataset.y, inside = y >= lo && y <= hi;
        d.hidden = !inside; if (!inside) return;
        var x = pct(y) / 100 * width, r = 0;
        while (rows[r] !== undefined && x - rows[r] < GAP) r++;
        rows[r] = x;
        d.style.left = pct(y) + '%'; d.style.top = (6 + r * ROW) + 'px';
      }});
      lane.style.height = (30 + Math.max(rows.length - 1, 0) * ROW) + 'px';
    }});
    [].forEach.call(evs.querySelectorAll('.tl-ev'), function (b) {{
      var y = +b.dataset.y; b.hidden = y < lo || y > hi;
    }});
  }}
  function setRange(pid) {{
    if (!pid) range = TL_FULL.slice();
    else {{ var p = PERIODS[pid], pad = Math.max(3, (p[1] - p[0]) * .04); range = [p[0] - pad, p[1] + pad]; }}
    [].forEach.call(zoom.querySelectorAll('button'), function (b) {{
      var on = b.dataset.p === (pid || ''); b.classList.toggle('on', on); b.setAttribute('aria-pressed', on);
    }});
    layout();
  }}
  function show(id) {{
    var d = EVENTS[id]; if (!d) return;
    selId = id;
    [].forEach.call(document.querySelectorAll('.tl-dot, .tl-ev'), function (x) {{
      x.classList.toggle('sel', x.dataset.ev === id);
    }});
    box.innerHTML = '<h3><a href="event/' + id + '/">' + d.name + '</a></h3>' +
      '<div class="ev-meta"><span>' + d.yr + '</span><span class="tag">' + d.type + '</span>' +
      '<span class="tag tag-rel" data-rel="' + d.rel + '">' + d.rel + '</span>' +
      d.states.map(function (s) {{ return '<span class="tag tag-state">' + s + '</span>'; }}).join('') +
      '</div><div class="ev-sig">' + d.sig + '</div>' +
      (d.idioms.length ? '<div class="ev-idioms">' + d.idioms.map(function (i) {{
        return '<a href="idioms/' + i.id + '/">' + i.zh + '</a>';
      }}).join('') + '</div>' : '') +
      '<a class="ev-more" href="event/' + id + '/">閱讀事件全文 →</a>';
  }}
  zoom.addEventListener('click', function (ev) {{
    var b = ev.target.closest('button'); if (b) setRange(b.dataset.p);
  }});
  document.addEventListener('click', function (ev) {{
    var seg = ev.target.closest('.tl-periods .seg');
    if (seg) {{ setRange(seg.dataset.p); return; }}
    var t = ev.target.closest('.tl-dot, .tl-ev'); if (!t) return;
    show(t.dataset.ev);
    if (t.classList.contains('tl-dot')) box.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
  }});
  var rt; window.addEventListener('resize', function () {{ clearTimeout(rt); rt = setTimeout(layout, 120); }});
  layout();
}})();
</script>"""
    return page("時間 × 列國 年表", body, current="timeline.html", canonical="timeline.html",
                desc="以時間為橫軸、列國為縱軸的春秋戰國二維年表；可按分期放大，晉分三家、田氏代齊皆在圖上可見。")


# ────────────────────────── 成語索引 ──────────────────────────

def build_idioms_index(data):
    idioms = sorted(data["idioms"].values(), key=sort_key_idiom)

    def idx_card(d):
        k = " ".join([d["idiom"]["zh"], d["idiom"]["pinyin"], plain_pinyin(d["idiom"]["pinyin"]),
                      d.get("meaning", "")])
        return idiom_card(d, data).replace('<div class="card-wrap">',
                                           f'<div class="card-wrap idx-item" data-id="{e(d["id"])}" data-k="{e(k)}">', 1)

    def section(gid, key, title, sub, items):
        anchor = f"{gid}-{key}"
        cards = "".join(idx_card(d) for d in items)
        return (anchor, title, len(items),
                f'<section class="idx-sec" id="{e(anchor)}">'
                f'<h2 class="section-title">{e(title)}'
                f'<span class="count">{len(items)} 條</span>'
                f'<span class="sub">{e(sub)}</span></h2>'
                f'<div class="grid">{cards}</div></section>')

    groups = {}
    # 按分期
    groups["period"] = [section("p", p["id"], p["name"], f'前 {abs(p["start"])} – 前 {abs(p["end"])}',
                                [d for d in idioms if d.get("period") == p["id"]])
                        for p in data["periods"]
                        if any(d.get("period") == p["id"] for d in idioms)]
    # 按文獻（以第一條典源為準）
    src_groups = {}
    for d in idioms:
        src_groups.setdefault((d.get("dianyuan") or [{}])[0].get("source"), []).append(d)
    groups["source"] = [section("s", sid, f'《{data["sources"].get(sid, {}).get("name", sid)}》',
                                data["sources"].get(sid, {}).get("locus_format", ""), items)
                        for sid, items in sorted(src_groups.items(), key=lambda kv: -len(kv[1]))]
    # 按可信度
    hints = {
        "信史": "同期或近期文獻互證，可繫年繫人",
        "大體可信": "主源可信，細節有後世增飾",
        "孤證": "僅一書所載，別無旁證",
        "後世附會": "晚出，或與早期文獻／出土材料相牴",
        "寓言": "諸子所設之譬喻，本無其事",
    }
    groups["rel"] = [section("r", str(i), r, hints[r], [d for d in idioms if d["reliability"] == r])
                     for i, r in enumerate(hints) if any(d["reliability"] == r for d in idioms)]
    # 按列國
    lane_states = sorted([s for s in data["states"].values() if s.get("lane")],
                         key=lambda s: s.get("lane_order", 99))
    groups["state"] = [section("c", st["id"], st["name"], st.get("note", "")[:60],
                               [d for d in idioms if st["id"] in (d.get("states") or [])])
                       for st in lane_states
                       if any(st["id"] in (d.get("states") or []) for d in idioms)]

    def short(label):
        return label.split("・")[0] if "・" in label else label

    names = [("period", "按分期"), ("source", "按文獻"), ("rel", "按可信度"), ("state", "按列國")]
    navs = "".join(jump_nav([(a, short(t), n) for a, t, n, _ in groups[g]], group=g, hidden=(g != "period"))
                   for g, _ in names)
    buttons = "".join(f'<button type="button" data-g="{g}" aria-pressed="{str(g == "period").lower()}"'
                      f'{ON_CLS if g == "period" else ""}>{label}</button>' for g, label in names)
    controls = f'<div class="idx-groups" id="idxGroups" role="group" aria-label="分組方式">{buttons}</div>'
    containers = "".join(
        f'<div id="g-{g}" data-idx-scope{"" if g == "period" else " hidden"}>'
        f'{"".join(html_ for *_, html_ in groups[g])}</div>'
        for g, _ in names)

    body = f"""<main>
<div class="page-head">
  <h1>成語索引</h1>
  <p class="lede">同一批條目，四種切法：按分期看歷史脈絡，按文獻看史料分佈，
  按可信度看哪些可作史實、哪些只能作思想史材料，按列國看地緣。可輸入成語、拼音或釋義篩選。</p>
</div>
{idx_toolbar(navs, "篩選：成語、拼音或釋義", controls)}
{containers}
<p class="idx-empty" id="idxEmpty" hidden>沒有相符的成語。</p>
</main>
{INDEX_JS}"""
    return page("成語索引", body, current="idioms.html", canonical="idioms.html",
                desc="全部成語條目，可按分期、文獻、史料可信度、列國四種方式分組瀏覽，並可即時篩選。")


# ────────────────────────── 編年大事（索引） ──────────────────────────

def build_events(data):
    ev_idioms = event_idioms(data)
    sections, nav = "", []
    for p in data["periods"]:
        evs = [ev for ev in ordered_events(data)
               if p["start"] <= (year_num(ev.get("year")) or 0) <= p["end"]]
        if not evs:
            continue
        rows = ""
        for ev in evs:
            states = [data["states"][s]["name"] for s in ev.get("states", []) if s in data["states"]]
            ids = ev_idioms.get(ev["id"], [])
            ppl = [data["people"][x]["name"]["zh"] for x in ev.get("people") or [] if x in data["people"]]
            k = " ".join([ev["name"], ev["type"], ev_year_label(ev), *states, *ppl,
                          *(d["idiom"]["zh"] for d in ids)])
            id_links = "".join(f'<a class="tag tag-type" href="idioms/{e(d["id"])}/">{e(d["idiom"]["zh"])}</a>'
                               for d in ids)
            st_tags = "".join(f'<span class="tag tag-state">{e(s)}</span>' for s in states)
            rows += f"""<div class="ev-item idx-item" data-k="{e(k)}" data-type="{e(ev['type'])}" data-st="{e(' '.join(ev.get('states') or []))}">
  <span class="yr">{e(ev_year_label(ev))}</span>
  <span class="main">
    <h3><a class="stretch" href="{ev_url(ev['id'])}">{e(ev['name'])}</a></h3>
    <span class="sub">{rich(ev.get('significance', ''))}</span>
    <span class="tags"><span class="tag">{e(ev['type'])}</span>{st_tags}{id_links}</span>
  </span>
</div>"""
        anchor = f"p-{p['id']}"
        nav.append((anchor, p["name"].split("・")[0], len(evs)))
        sections += (f'<section class="idx-sec" id="{e(anchor)}">'
                     f'<h2 class="section-title">{e(p["name"])}'
                     f'<span class="count">{len(evs)} 事</span>'
                     f'<span class="sub">前 {abs(p["start"])} – 前 {abs(p["end"])}</span></h2>'
                     f'<div class="ev-list">{rows}</div></section>')

    types = sorted({ev["type"] for ev in data["events"].values()})
    used_states = {s for ev in data["events"].values() for s in ev.get("states") or []}
    lane = sorted([s for s in data["states"].values() if s["id"] in used_states],
                  key=lambda s: (0 if s.get("lane") else 1, s.get("lane_order", 99)))
    controls = (idx_select("type", "類型", [(t, t) for t in types]) +
                idx_select("st", "列國", [(s["id"], s["name"]) for s in lane]))
    body = f"""<main>
<div class="page-head">
  <h1>編年大事</h1>
  <p class="lede">按分期排列的事件骨幹，點選事件名稱閱讀全文。每事列出所繫的成語——
  一個事件可以生出多條成語（城濮之戰生出退避三舍與表裡山河）。</p>
</div>
{idx_toolbar(jump_nav(nav), "篩選：事件、人物或成語", controls)}
<div data-idx-scope>{sections}</div>
<p class="idx-empty" id="idxEmpty" hidden>沒有相符的事件。</p>
</main>
{INDEX_JS}"""
    return page("編年大事", body, current="events.html", canonical="events.html",
                desc="春秋戰國編年大事表，按七個分期排列，可按類型、列國篩選；每事另有獨立頁面。")


# ────────────────────────── 人物（索引） ──────────────────────────

def build_people(data):
    p_idioms = person_idioms(data)
    sections, nav = "", []
    for st, ppl in ordered_people(data):
        cards = ""
        for pr in ppl:
            ids = [d["idiom"]["zh"] for d in p_idioms.get(pr["id"], [])]
            k = " ".join([pr["name"]["zh"], pr["name"].get("en", ""), pr["name"].get("personal", "") or "",
                          pr["role"], st["name"], *ids])
            cards += (f'<a class="pp-card idx-item" href="{person_url(pr["id"])}" data-k="{e(k)}" '
                      f'data-role="{e(pr["role"])}">'
                      f'<span class="nm">{e(pr["name"]["zh"])}</span>'
                      f'<span class="meta">{e(person_years(pr))}・{e(pr["role"])}</span>'
                      f'<span class="ids">{e("・".join(ids))}</span></a>')
        anchor = f"s-{st['id']}"
        nav.append((anchor, st["name"], len(ppl)))
        sections += (f'<section class="idx-sec" id="{e(anchor)}">'
                     f'<h2 class="section-title">{e(st["name"])}'
                     f'<span class="count">{len(ppl)} 人</span>'
                     f'<span class="sub">{e((st.get("note") or "")[:60])}</span></h2>'
                     f'<div class="pp-grid">{cards}</div></section>')

    roles = [r for r, _ in sorted(
        {p["role"]: 0 for p in data["people"].values()}.items())]
    order = ["君主", "卿大夫", "將領", "策士", "思想家"]
    roles.sort(key=lambda r: (order.index(r) if r in order else 99, r))
    controls = idx_select("role", "身分", [(r, r) for r in roles])
    body = f"""<main>
<div class="page-head">
  <h1>人物</h1>
  <p class="lede">按所屬列國分組，國內按生年排序；點選人名閱讀小傳。生卒不可考者以「？」標示。
  先秦思想家的思想部分外連至<a href="https://cc-philosophy.vercel.app/" target="_blank" rel="noopener">哲學家知識庫</a>。</p>
</div>
{idx_toolbar(jump_nav(nav), "篩選：人名、國名或成語", controls)}
<div data-idx-scope>{sections}</div>
<p class="idx-empty" id="idxEmpty" hidden>沒有相符的人物。</p>
</main>
{INDEX_JS}"""
    return page("人物", body, current="people.html", canonical="people.html",
                desc="春秋戰國人物索引，按列國分組，可按身分篩選；每人另有小傳頁面。")


# ────────────────────────── 事件頁、人物頁 ──────────────────────────

def crumbs(up, *parts):
    links = "".join(f'<a href="{up}{href}">{e(label)}</a><span class="sep">›</span>' for href, label in parts)
    return f'<nav class="crumbs">{links}</nav>'


def build_event_page(ev, data, prev_ev, next_ev, ev_idioms):
    up = "../../"
    per = data["period_by_id"].get(ev.get("period"), {})
    states = "".join(f'<span class="tag tag-state">{e(data["states"][s]["name"])}</span>'
                     for s in ev.get("states", []) if s in data["states"])
    year_note = f'・{e(ev["year_note"])}' if ev.get("year_note") else ""
    blocks = event_original_blocks(ev, data)
    ids = ev_idioms.get(ev["id"], [])
    ppl = "".join(f'<a href="{person_url(pid, up)}">{e(data["people"][pid]["name"]["zh"])}</a>'
                  for pid in ev.get("people") or [] if pid in data["people"])
    variants = ""
    for v in ev.get("variants") or []:
        src = data["sources"].get(v.get("source"), {})
        variants += (f'<div class="variant">{rich(v.get("claim"))}'
                     f'<div class="src">——《{e(src.get("name", v.get("source")))}》{e(v.get("locus", ""))}</div></div>')
    srcs = "".join(f"<li>{cite_line(c, data)}</li>" for c in ev.get("sources") or [])

    prevnext = '<div class="prevnext">'
    prevnext += (f'<a href="{ev_url(prev_ev["id"], up)}">← {e(prev_ev["name"])}</a>' if prev_ev else "<span></span>")
    prevnext += (f'<a href="{ev_url(next_ev["id"], up)}">{e(next_ev["name"])} →</a>' if next_ev else "<span></span>")
    prevnext += "</div>"

    body = f"""<main class="narrow">
{crumbs(up, ("events.html", "編年大事"), (f"events.html#p-{ev.get('period')}", per.get("name", "")))}
<div class="idiom-hero ev-hero">
  <h1>{e(ev['name'])}</h1>
  <div class="romanisation">{e(ev_year_label(ev))}{year_note}</div>
  <div class="meaning">{rich(ev.get('significance', ''))}</div>
  <div class="tags"><span class="tag">{e(ev['type'])}</span>{rel_tag(ev['reliability'])}
    <span class="tag">{e(per.get('name', ''))}</span>{states}</div>
</div>
<section class="layer"><h2>經過</h2><div class="narrative">{paras(ev.get('narrative'))}</div></section>
{f'<section class="layer"><h2>原文選段<span class="hint">白話在上，原文在下</span></h2>{blocks}</section>' if blocks else ''}
{f'<section class="layer"><h2>所繫成語</h2><div class="grid">{"".join(idiom_card(d, data, up) for d in ids)}</div></section>' if ids else ''}
{f'<section class="layer"><h2>相關人物</h2><div class="rel-links">{ppl}</div></section>' if ppl else ''}
{f'<section class="layer"><h2>異說</h2>{variants}</section>' if variants else ''}
{f'<section class="layer"><h2>附註</h2><p class="notes-body">{rich(ev.get("notes"))}</p></section>' if ev.get('notes') else ''}
{f'<section class="layer"><h2>出處</h2><ul class="refs src-list">{srcs}</ul></section>' if srcs else ''}
{prevnext}
</main>"""
    return page(ev["name"], body, current="events.html", depth=2, canonical=ev_url(ev["id"]),
                desc=f"{ev['name']}（{ev_year_label(ev)}）：{re.sub(r'[*]', '', ev.get('significance', ''))[:80]}")


REL_KIND = {"ruler": "其君", "minister": "其臣", "kin": "親屬", "teacher": "師從",
            "rival": "政敵", "ally": "盟友"}
REL_REVERSE = {"ruler": "其臣", "minister": "其君", "kin": "親屬", "teacher": "弟子",
               "rival": "政敵", "ally": "盟友"}


def person_relations(data):
    """正向關聯；對方未寫明者自動補上反向關聯。
    relations.note 屬編者筆記（半文言），不在頁面顯示；timeline、notes 已改寫為白話，照常顯示。"""
    out = {pid: [] for pid in data["people"]}
    for pr in data["people"].values():
        for r in pr.get("relations") or []:
            t = r.get("target")
            if t not in data["people"]:
                continue
            out[pr["id"]].append((t, REL_KIND.get(r["kind"], r["kind"])))
    for pr in data["people"].values():
        for r in pr.get("relations") or []:
            t = r.get("target")
            if t in out and not any(x[0] == pr["id"] for x in out[t]):
                out[t].append((pr["id"], REL_REVERSE.get(r["kind"], r["kind"])))
    return out


def build_person_page(pr, data, prev_p, next_p, p_idioms, p_events, relations):
    up = "../../"
    st = data["states"].get(pr["state"], {})
    phil = ""
    if pr.get("philosophy_ref"):
        phil = (f'<section class="layer"><h2>思想</h2><p class="notes-body">本站不重寫先秦思想家的學說，'
                f'請參閱<a href="https://cc-philosophy.vercel.app/philosophers/{e(pr["philosophy_ref"])}/" '
                f'target="_blank" rel="noopener">哲學家知識庫的{e(pr["name"]["zh"])}條目 ↗</a>。</p></section>')
    tl = "".join(f'<div class="pt-row"><span class="yr">{e(year_label(t.get("year")))}</span>'
                 f'<span>{rich(t.get("event", ""))}</span></div>' for t in pr.get("timeline") or [])
    rels = "".join(f'<a href="{person_url(t, up)}">{e(data["people"][t]["name"]["zh"])}'
                   f'<span class="kind">{e(kind)}</span></a>'
                   for t, kind in relations.get(pr["id"], []))
    evs = "".join(f'<a href="{ev_url(ev["id"], up)}">{e(ev["name"])}'
                  f'<span class="kind">{e(year_label(ev.get("year")))}</span></a>'
                  for ev in p_events.get(pr["id"], []))
    ids = p_idioms.get(pr["id"], [])
    srcs = "".join(f"<li>{cite_line(c, data)}</li>" for c in pr.get("sources") or [])
    en = f'<span class="p-en">{e(pr["name"]["en"])}</span>' if pr["name"].get("en") else ""

    prevnext = '<div class="prevnext">'
    prevnext += (f'<a href="{person_url(prev_p["id"], up)}">← {e(prev_p["name"]["zh"])}</a>' if prev_p else "<span></span>")
    prevnext += (f'<a href="{person_url(next_p["id"], up)}">{e(next_p["name"]["zh"])} →</a>' if next_p else "<span></span>")
    prevnext += "</div>"

    body = f"""<main class="narrow">
{crumbs(up, ("people.html", "人物"), (f"people.html#s-{pr['state']}", st.get("name", "")))}
<div class="idiom-hero ev-hero">
  <h1>{e(pr['name']['zh'])}</h1>
  <div class="romanisation">{en}</div>
  <div class="tags"><span class="tag tag-state">{e(st.get('name', ''))}</span><span class="tag">{e(pr['role'])}</span>
    <span class="tag">{e(person_years(pr))}</span></div>
</div>
<section class="layer"><h2>小傳</h2><div class="narrative bio">{paras(pr.get('bio'))}</div></section>
{f'<section class="layer"><h2>生平</h2><div class="pt-list">{tl}</div></section>' if tl else ''}
{phil}
{f'<section class="layer"><h2>相關成語</h2><div class="grid">{"".join(idiom_card(d, data, up) for d in ids)}</div></section>' if ids else ''}
{f'<section class="layer"><h2>相關事件</h2><div class="rel-links">{evs}</div></section>' if evs else ''}
{f'<section class="layer"><h2>相關人物</h2><div class="rel-links">{rels}</div></section>' if rels else ''}
{f'<section class="layer"><h2>附註</h2><p class="notes-body">{rich(pr.get("notes"))}</p></section>' if pr.get('notes') else ''}
{f'<section class="layer"><h2>出處</h2><ul class="refs src-list">{srcs}</ul></section>' if srcs else ''}
{prevnext}
</main>"""
    return page(pr["name"]["zh"], body, current="people.html", depth=2, canonical=person_url(pr["id"]),
                desc=f"{pr['name']['zh']}（{st.get('name', '')}・{pr['role']}）小傳、相關事件與成語。")



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
                        f'rel="noopener" class="src-link">ctext ↗</a>')
            meta = []
            if s.get("compiled") is not None:
                meta.append(f'成書約{year_label(s["compiled"])}')
            if s.get("compiler"):
                meta.append(e(s["compiler"]))
            if s.get("excavated"):
                meta.append(f'{s["excavated"]} 年出土')
            caveat = (f'<div class="caveat"><b>須注意：</b>{e(s["caveat"])}</div>'
                      if s.get("caveat") else "")
            cards += f"""<div class="src-card" id="{e(s['id'])}">
  <div class="top"><h3>《{e(s['name'])}》</h3>
    <span class="src-meta">{e("・".join(meta))}</span>{link}{badge}</div>
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

    layers = []      # 可讀部分：本事（白話故事）
    kaoju = []       # 考據部分：典源、語形定型、可信度——供查證，不是主線閱讀

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
  <div class="sub-label">所繫事件</div>
  <div class="ev-name"><a href="{ev_url(ev['id'], up)}">{e(ev['name'])}</a>
    <span class="ev-year">（{e(yl)}）</span></div>
  <div class="narrative">{paras(ev.get('narrative'))}</div>{event_originals(ev, data)}
  <div class="significance"><b>意義：</b>{rich(ev.get('significance', ''))}</div>
</div>"""
        layers.append(f"""<section class="layer">
  <h2><span class="num">第一層</span>本事<span class="hint">歷史上實際發生了甚麼</span></h2>
  <p class="benshi-summary">{rich(benshi.get('summary'))}</p>
  {ev_html}
</section>""")
    else:
        layers.append(f"""<section class="layer">
  <h2><span class="num">第一層</span>本事<span class="hint">歷史上實際發生了甚麼</span></h2>
  <p class="parable-note">
  本條是<b>寓言</b>——諸子用來說理的比喻，並沒有真實發生過的本事。
  它的史料價值不在於記錄了甚麼事，而在於顯示了那個時代的人怎樣講道理。</p>
</section>""")

    # 第二層：典源
    quotes = "".join(quote_block(c, data) for c in d.get("dianyuan") or [])
    kaoju.append(f"""<section class="layer">
  <h2><span class="num">第二層</span>典源<span class="hint">最早見於哪本書、哪一段</span></h2>
  {quotes}
</section>""")

    # 第三層：語形定型
    cry = d.get("crystallisation")
    if cry:
        fa = (f'<div class="cryst-first">'
              f'四字語形最早可考：<b style="color:var(--bronze-deep)">{e(cry["first_attested"])}</b></div>'
              if cry.get("first_attested") else "")
        moe = ""
        if cry.get("moe_id"):
            moe = (f'<div class="moe-link">'
                   f'交叉核對：<a href="https://dict.idioms.moe.edu.tw/idiomView.jsp?ID={e(cry["moe_id"])}'
                   f'&webMd=1&la=0" target="_blank" rel="noopener">教育部《成語典》 ↗</a></div>')
        kaoju.append(f"""<section class="layer">
  <h2><span class="num">第三層</span>語形定型<span class="hint">「四字成語」這個形式何時確立</span></h2>
  {fa}
  <p class="cryst-note">{rich(cry.get('note'))}</p>
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
    kaoju.append(f"""<section class="layer">
  <h2><span class="num">第四層</span>可信度與異說<span class="hint">本事有多可信、有沒有相牴的記載</span></h2>
  <div style="display:flex;align-items:center;gap:11px;margin-bottom:11px">
    {rel_tag(d['reliability'])}<span class="rel-hint">{e(rel_hint)}</span>
  </div>
  {variants or '<p class="no-variant">未見相牴之記載。</p>'}
</section>""")

    # 啟示
    les = d.get("lessons") or {}
    modern = ""
    if les.get("modern"):
        modern = f"""<div class="box modern">
  <h3>現代引申</h3><p>{rich(les['modern'])}</p>
  <div class="caveat">※ 引申義，非史料本身所有。</div>
</div>"""
    lessons_html = f"""<section class="layer">
  <h2>啟示<span class="hint">史觀分析與現代引申分開處理</span></h2>
  <div class="lessons">
    <div class="box"><h3>史觀</h3><p>{rich(les.get('historical'))}</p></div>
    {modern}
  </div>
</section>"""

    # 關聯
    kind_label = {"same_event": "同一事件", "same_source": "同一典源",
                  "contrast": "意義相對", "derived": "由此衍生",
                  "sequel": "前後相承", "parallel": "相互參照"}
    rel_html = ""
    for r in d.get("_related") or []:
        t = data["idioms"][r["target"]]
        rel_html += (f'<a href="{up}idioms/{e(t["id"])}/">{e(t["idiom"]["zh"])}'
                     f'<span class="kind">{e(kind_label.get(r["kind"], r["kind"]))}</span></a>')
    ppl_html = "".join(
        f'<a href="{person_url(pid, up)}">{e(data["people"][pid]["name"]["zh"])}</a>'
        for pid in d.get("people") or [] if pid in data["people"]
    )
    rel_section = f"""<section class="layer">
  <h2>關聯</h2>
  {f'<div class="sub-label">相關成語</div><div class="rel-links" style="margin-bottom:14px">{rel_html}</div>' if rel_html else ''}
  <div class="sub-label">相關人物</div>
  <div class="rel-links">{ppl_html}</div>
</section>"""

    refs = "".join(f'<li><a href="{e(u)}" target="_blank" rel="noopener">{e(u)}</a></li>'
                   for u in d.get("references") or [])
    notes = (f'<section class="layer"><h2>附註</h2>'
             f'<p class="notes-body">{rich(d.get("notes"))}</p></section>'
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
  <div class="romanisation">{e(d['idiom']['pinyin'])}{jyut}
    {say_button(d['id'], up, d['idiom']['zh'])}</div>
  <div class="literal"><b>字面</b>　{e(d['idiom']['literal'])}　·　{e(d['idiom']['en'])}</div>
  <div class="meaning">{e(d.get('meaning'))}</div>
  <div class="tags">
    {type_tag(d['type'])}{'' if d['reliability'] == '寓言' else rel_tag(d['reliability'])}
    <span class="tag">{e(per.get('name', ''))}</span>
    <span class="tag">{e(year_label(d.get('year')))}{('・' + e(d['year_note'])) if d.get('year_note') else ''}</span>
    {states}{concepts}
  </div>
</div>
{''.join(layers)}
<section class="layer"><h2>論述<span class="hint">這件事說明了甚麼</span></h2>
  <div class="essay">{essay}</div></section>
{lessons_html}
<div class="kaoju-divider">
  <span class="kd-label">考據</span>
  <p class="kd-hint">以下為文獻依據，供查證之用。原文一律附白話今譯，不讀原文亦不影響理解。</p>
</div>
{''.join(kaoju)}
{rel_section}
{notes}
<section class="layer"><h2>撰寫依據</h2><ul class="refs">{refs}</ul></section>
{prevnext}
</main>"""
    return page(d["idiom"]["zh"], body, current="idioms.html", depth=2,
                canonical=f"idioms/{d['id']}/",
                desc=f"{d['idiom']['zh']}——{d.get('meaning')}本事、典源、語形定型與史料可信度四層考據。")


# ────────────────────────── 搜尋索引 ──────────────────────────

def plain_pinyin(py):
    """去掉拼音聲調符號（wò xīn → wo xin），讓搜尋時不必輸入聲調。"""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", py) if not unicodedata.combining(c)).replace("ü", "v")


def build_search_index(data):
    rows = []
    for d in sorted(data["idioms"].values(), key=sort_key_idiom):
        per = data["period_by_id"].get(d.get("period"), {})
        rows.append({
            "t": d["idiom"]["zh"], "c": "成語", "u": f"idioms/{d['id']}/",
            "s": f"{year_label(d.get('year'))}・{per.get('name','')}",
            "k": " ".join([d["idiom"]["zh"], d["idiom"]["pinyin"], plain_pinyin(d["idiom"]["pinyin"]),
                           d["idiom"].get("jyutping", ""),
                           d.get("meaning", ""), " ".join(d.get("concepts") or [])]),
        })
    for ev in sorted(data["events"].values(), key=lambda x: year_num(x.get("year")) or 0):
        rows.append({
            "t": ev["name"], "c": "事件", "u": ev_url(ev['id']),
            "s": year_label(ev.get("year")),
            "k": " ".join([ev["name"], ev.get("significance", "")]),
        })
    for pr in data["people"].values():
        rows.append({
            "t": pr["name"]["zh"], "c": "人物", "u": person_url(pr['id']),
            "s": f'{data["states"].get(pr["state"], {}).get("name", "")}・{pr["role"]}',
            "k": " ".join([pr["name"]["zh"], pr["name"].get("en", ""),
                           pr["name"].get("personal", "") or "", (pr.get("bio") or "")[:80]]),
        })
    for s in data["sources"].values():
        rows.append({
            "t": f'《{s["name"]}》', "c": "文獻", "u": f"sources.html#{s['id']}",
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

    # 事件頁（按年序前後翻頁）、人物頁（按列國、生年前後翻頁）
    evs = ordered_events(data)
    ev_ids = event_idioms(data)
    for i, ev in enumerate(evs):
        write(f"event/{ev['id']}/index.html",
              build_event_page(ev, data, evs[i - 1] if i else None,
                               evs[i + 1] if i < len(evs) - 1 else None, ev_ids))
    ppl = [p for _, group in ordered_people(data) for p in group]
    p_ids, p_evs, rels = person_idioms(data), person_events(data), person_relations(data)
    for i, pr in enumerate(ppl):
        write(f"person/{pr['id']}/index.html",
              build_person_page(pr, data, ppl[i - 1] if i else None,
                                ppl[i + 1] if i < len(ppl) - 1 else None, p_ids, p_evs, rels))

    # 404 / robots / sitemap / .nojekyll
    write("404.html", page("找不到頁面", """<main class="narrow">
<div class="page-head"><h1>找不到這一頁</h1>
<p class="lede">網址可能已經變更，或者這一條還沒收錄。
可以回<a href="index.html">總覽</a>看看，或者按 <kbd>/</kbd> 全站搜尋。</p></div></main>"""))
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    today = date.today().isoformat()
    urls = ["", "timeline.html", "idioms.html", "events.html", "people.html", "sources.html"]
    urls += [f"idioms/{d['id']}/" for d in ordered]
    urls += [ev_url(ev["id"]) for ev in evs] + [person_url(p["id"]) for p in ppl]
    sm = "\n".join(
        f"  <url><loc>{SITE_URL}/{u}</loc><lastmod>{today}</lastmod></url>" for u in urls)
    write("sitemap.xml",
          f'<?xml version="1.0" encoding="UTF-8"?>\n'
          f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{sm}\n</urlset>\n')
    (ROOT / ".nojekyll").touch()

    print(f"生成完成：成語頁 {counts['n_idioms']}、事件頁 {counts['n_events']}、"
          f"人物頁 {counts['n_people']}，另 6 個索引頁")


if __name__ == "__main__":
    main()
