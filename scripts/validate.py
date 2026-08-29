#!/usr/bin/env python3
"""驗證 idioms / events / people 三種條目符合 schema，並檢查四層 id 空間嘅交叉引用。

id 空間：
    成語  idioms/<id>/profile.yaml  （主條目，另須有 <id>.md）
    事件  events/<id>.yaml
    人物  people/<id>.yaml
    參照  data/{states,sources,periods}.yaml

檢查項目：
  通用   必填欄位齊全；id 同檔名／目錄名一致；year 為整數或 "c. -632" 式字串
  成語   type/reliability/kind 取值合法；type: historical 必須有 benshi 同 year；
         reliability: 寓言 必須配 type: parable（反之亦然）；
         dianyuan 每條有 source/locus/quote/translation，source 存在於 data/sources.yaml；
         ctext_urn 格式為 ctp:<book>/<chapter> 且 book 對得上該文獻嘅 ctext slug；
         states/period/people/benshi.event 全部指向已存在嘅 id；
         related_idioms.target 存在、唔指向自己、kind 合法；
         lessons.historical 必填
  事件   states/people/period/sources 交叉引用；type 取值合法；timeline 年份合理
  人物   state/role 合法；timeline 按年份升序；relations.target 存在

用法：python3 scripts/validate.py
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
IDIOMS_DIR = ROOT / "idioms"
EVENTS_DIR = ROOT / "events"
PEOPLE_DIR = ROOT / "people"
DATA_DIR = ROOT / "data"

IDIOM_TYPES = {"historical", "parable"}
RELIABILITY = {"信史", "大體可信", "孤證", "後世附會", "寓言"}
REL_KINDS = {"same_event", "same_source", "contrast", "derived"}
EVENT_TYPES = {"戰役", "會盟", "變法", "弒君篡位", "遷都", "外交",
               "滅國", "內亂", "出奔", "刺殺", "著述", "拜相",
               "行賞", "論政", "獻策"}
PERSON_ROLES = {"君主", "卿大夫", "策士", "將領", "思想家",
                "刺客", "工匠", "隱士", "商人", "樂師", "醫者"}
PERSON_REL_KINDS = {"ruler", "minister", "kin", "teacher", "rival", "ally"}

IDIOM_REQUIRED = ["id", "idiom", "type", "period", "states",
                  "meaning", "dianyuan", "reliability", "people",
                  "concepts", "lessons", "references"]
EVENT_REQUIRED = ["id", "name", "year", "period", "type", "states",
                  "people", "narrative", "sources", "reliability",
                  "significance"]
# birth / death 唔列入呢度：佢哋容許 null（生卒不可考），
# 只檢查欄位有冇出現，見 check_person
PERSON_REQUIRED = ["id", "name", "state", "role", "bio", "sources"]

YEAR_RE = re.compile(r"^c\. -?\d+$")
# 文言引語（含文言虛詞、長度 ≥16）之後應緊接「（白話：…）」今譯
QUOTE_RE = re.compile(r"「[^「」]*(?:『[^』]*』[^「」]*)*」")
GLOSS_RE = re.compile(r"\s*（\s*白\s*話\s*：")
FUNCTION_WORDS = re.compile(r"[之乎者也矣焉曰其於弗勿毋豈奚胡寡臣]")
# 篇章可以有多層（例：呂氏春秋 shen-da-lan/cha-jin、晏子春秋 nei-pian/za-xia）
URN_RE = re.compile(r"^ctp:([a-z0-9-]+)/([a-z0-9-]+(?:/[a-z0-9-]+)*)$")


warnings: list[str] = []          # 白話今譯之類嘅提示，唔阻擋建置


def load(path: Path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def year_ok(value) -> bool:
    """年份可以係整數、"c. -632" 式約數，或 null。"""
    if value is None or isinstance(value, int):
        return True
    return isinstance(value, str) and bool(YEAR_RE.match(value))


def year_value(value):
    """取年份嘅數值，供排序檢查用；不可考者當作 None。"""
    if isinstance(value, int):
        return value
    if isinstance(value, str) and YEAR_RE.match(value):
        return int(value.split()[-1])
    return None


def missing_gloss(text, label):
    """文言引語冇今譯者，回傳警告（唔算錯誤，只提示）。"""
    warns = []
    for m in QUOTE_RE.finditer(text or ""):
        q = m.group()
        if len(q) < 16 or not FUNCTION_WORDS.search(q):
            continue
        if GLOSS_RE.match((text or "")[m.end():m.end() + 8]):
            continue
        warns.append(f"{label} 有文言引語未附白話：{q[:24]}…")
    return warns


def check_required(data: dict, fields: list[str]) -> list[str]:
    return [f"缺少必填欄位: {f}" for f in fields
            if f not in data or data[f] in (None, [], "")]


def check_citations(items, label, sources, errors):
    """檢查 dianyuan / sources / variants 呢類引用陣列。"""
    for i, cite in enumerate(items or []):
        where = f"{label}[{i}]"
        src = cite.get("source")
        if not src:
            errors.append(f"{where} 缺 source")
        elif src not in sources:
            errors.append(f"{where} source '{src}' 唔喺 data/sources.yaml")
        if not cite.get("locus"):
            errors.append(f"{where} 缺 locus")

        urn = cite.get("ctext_urn")
        if urn:
            m = URN_RE.match(urn)
            if not m:
                errors.append(f"{where} ctext_urn 格式錯誤: {urn}"
                              f"（應為 ctp:<書>/<篇章>）")
            elif src in sources:
                expected = sources[src].get("ctext")
                if not expected:
                    errors.append(
                        f"{where} 文獻 '{src}' 喺 data/sources.yaml 冇 ctext slug，"
                        f"唔應該有 ctext_urn")
                elif m.group(1) != expected:
                    errors.append(
                        f"{where} ctext_urn 嘅書 '{m.group(1)}' "
                        f"同 '{src}' 嘅 ctext slug '{expected}' 唔一致")


def check_idiom(path: Path, ids) -> list[str]:
    data = load(path)
    errors = check_required(data, IDIOM_REQUIRED)
    if errors:
        return errors

    dirname = path.parent.name
    if data["id"] != dirname:
        errors.append(f"id ({data['id']}) 同目錄名 ({dirname}) 唔一致")

    idiom = data["idiom"] or {}
    for key in ("zh", "pinyin", "literal", "en"):
        if not idiom.get(key):
            errors.append(f"idiom.{key} 缺失")
    if idiom.get("zh") and len(idiom["zh"]) < 3:
        errors.append(f"idiom.zh '{idiom['zh']}' 過短，本站只收四字（或以上）成語")

    itype = data["type"]
    if itype not in IDIOM_TYPES:
        errors.append(f"type 值無效: {itype}")

    reliability = data["reliability"]
    if reliability not in RELIABILITY:
        errors.append(f"reliability 值無效: {reliability}")

    # 寓言型同「寓言」可信度必須配對
    if itype == "parable" and reliability != "寓言":
        errors.append(f"type: parable 應配 reliability: 寓言（現為 {reliability}）")
    if reliability == "寓言" and itype != "parable":
        errors.append(f"reliability: 寓言 必須配 type: parable（現為 {itype}）")

    if itype == "historical":
        if not data.get("benshi"):
            errors.append("type: historical 必須有 benshi 欄")
        if data.get("year") is None:
            errors.append("type: historical 必須有 year（不可考者請改標 parable 或說明於 notes）")

    if "year" in data and not year_ok(data["year"]):
        errors.append(f"year 格式無效: {data['year']!r}（用整數、\"c. -632\" 或 null）")

    period = ids["periods"].get(data["period"])
    if period is None:
        errors.append(f"period '{data['period']}' 唔喺 data/periods.yaml")
    else:
        y = year_value(data.get("year"))
        if y is not None and not (period["start"] <= y <= period["end"]):
            errors.append(
                f"year {y} 唔喺 period '{data['period']}' 嘅範圍內"
                f"（{period['start']} – {period['end']}）")

    for st in data["states"] or []:
        if st not in ids["states"]:
            errors.append(f"states 有無效 id: {st}")

    benshi = data.get("benshi") or {}
    if benshi:
        ev = benshi.get("event")
        if not ev:
            errors.append("benshi 缺 event")
        elif ev not in ids["events"]:
            errors.append(f"benshi.event '{ev}' 喺 events/ 搵唔到")
        if not benshi.get("summary"):
            errors.append("benshi 缺 summary")

    for i, cite in enumerate(data["dianyuan"] or []):
        for key in ("quote", "translation"):
            if not cite.get(key):
                errors.append(f"dianyuan[{i}] 缺 {key}")
    check_citations(data["dianyuan"], "dianyuan", ids["sources"], errors)
    check_citations(data.get("variants"), "variants", ids["sources"], errors)

    cry = cryst = data.get("crystallisation")
    if cryst and not cryst.get("note"):
        errors.append("crystallisation 有欄但缺 note（須說明語形演變）")

    for p in data["people"] or []:
        if p not in ids["people"]:
            errors.append(f"people 有無效 id: {p}")

    for i, rel in enumerate(data.get("related_idioms") or []):
        target = rel.get("target")
        if not target:
            errors.append(f"related_idioms[{i}] 缺 target")
        elif target not in ids["idioms"]:
            errors.append(f"related_idioms[{i}] target '{target}' 唔係本站條目")
        elif target == data["id"]:
            errors.append(f"related_idioms[{i}] 唔可以指向自己")
        if rel.get("kind") not in REL_KINDS:
            errors.append(f"related_idioms[{i}] kind 值無效: {rel.get('kind')}")

    lessons = data["lessons"] or {}
    if not lessons.get("historical"):
        errors.append("lessons.historical 必填")

    md_path = path.parent / f"{data['id']}.md"
    if not md_path.exists():
        errors.append(f"缺少論述文章 {md_path.name}")

    warnings.extend(missing_gloss(benshi.get("summary"), "benshi.summary"))
    warnings.extend(missing_gloss((cry or {}).get("note"), "crystallisation.note"))
    warnings.extend(missing_gloss(lessons.get("historical"), "lessons.historical"))
    for i, v in enumerate(data.get("variants") or []):
        warnings.extend(missing_gloss(v.get("claim"), f"variants[{i}].claim"))
    return errors


def check_event(path: Path, ids) -> list[str]:
    data = load(path)
    errors = check_required(data, EVENT_REQUIRED)
    if errors:
        return errors

    if data["id"] != path.stem:
        errors.append(f"id ({data['id']}) 同檔名 ({path.stem}) 唔一致")

    if data["type"] not in EVENT_TYPES:
        errors.append(f"type 值無效: {data['type']}")
    if data["reliability"] not in RELIABILITY:
        errors.append(f"reliability 值無效: {data['reliability']}")
    if not year_ok(data["year"]):
        errors.append(f"year 格式無效: {data['year']!r}")
    if "year_end" in data and data["year_end"] is not None:
        if not year_ok(data["year_end"]):
            errors.append(f"year_end 格式無效: {data['year_end']!r}")
        else:
            start, end = year_value(data["year"]), year_value(data["year_end"])
            if start is not None and end is not None and end < start:
                errors.append(f"year_end ({end}) 早過 year ({start})")

    period = ids["periods"].get(data["period"])
    if period is None:
        errors.append(f"period '{data['period']}' 唔喺 data/periods.yaml")
    else:
        y = year_value(data.get("year"))
        if y is not None and not (period["start"] <= y <= period["end"]):
            errors.append(
                f"year {y} 唔喺 period '{data['period']}' 嘅範圍內"
                f"（{period['start']} – {period['end']}）")
    for st in data["states"] or []:
        if st not in ids["states"]:
            errors.append(f"states 有無效 id: {st}")
    for p in data["people"] or []:
        if p not in ids["people"]:
            errors.append(f"people 有無效 id: {p}")

    check_citations(data["sources"], "sources", ids["sources"], errors)
    check_citations(data.get("variants"), "variants", ids["sources"], errors)
    warnings.extend(missing_gloss(data.get("narrative"), "narrative"))
    return errors


def check_person(path: Path, ids) -> list[str]:
    data = load(path)
    errors = check_required(data, PERSON_REQUIRED)
    if errors:
        return errors

    if data["id"] != path.stem:
        errors.append(f"id ({data['id']}) 同檔名 ({path.stem}) 唔一致")

    name = data["name"] or {}
    for key in ("zh", "en"):
        if not name.get(key):
            errors.append(f"name.{key} 缺失")

    if data["state"] not in ids["states"]:
        errors.append(f"state '{data['state']}' 唔喺 data/states.yaml")
    if data["role"] not in PERSON_ROLES:
        errors.append(f"role 值無效: {data['role']}")

    for key in ("birth", "death"):
        if key not in data:
            errors.append(f"缺少欄位: {key}（不可考可寫 null）")
        elif not year_ok(data[key]):
            errors.append(f"{key} 格式無效: {data[key]!r}")

    if data.get("birth") is None and data.get("sort_year") is None:
        errors.append("birth 為 null 時須提供 sort_year 以供排序")

    years = []
    for i, item in enumerate(data.get("timeline") or []):
        if "year" not in item or "event" not in item:
            errors.append(f"timeline[{i}] 缺 year 或 event")
        elif not year_ok(item["year"]):
            errors.append(f"timeline[{i}] year 格式無效: {item['year']!r}")
        else:
            v = year_value(item["year"])
            if v is not None:
                years.append(v)
    if years != sorted(years):
        errors.append("timeline 未按年份升序排列")

    check_citations(data["sources"], "sources", ids["sources"], errors)

    for i, rel in enumerate(data.get("relations") or []):
        target = rel.get("target")
        if not target:
            errors.append(f"relations[{i}] 缺 target")
        elif target not in ids["people"]:
            errors.append(f"relations[{i}] target '{target}' 唔係本站人物")
        elif target == data["id"]:
            errors.append(f"relations[{i}] 唔可以指向自己")
        if rel.get("kind") not in PERSON_REL_KINDS:
            errors.append(f"relations[{i}] kind 值無效: {rel.get('kind')}")

    warnings.extend(missing_gloss(data.get("bio"), "bio"))
    return errors


LABEL_LEAK = re.compile(r"（(?:論述|敘事|小傳|欄位|今譯)）")
NESTED_GLOSS = re.compile(r"（白話：[^（）]*（白話：")
QUOTE_GLOSS_PAIR = re.compile(r"(「[^「」]{6,}」)\s*（白話：([^）]+)）")


def check_prose_integrity():
    """三種曾經真實發生過嘅錯誤，一律當作錯誤攔住：

      1. 審查流程漏出嘅段別標籤（論述）（欄位）等混入正文
      2. 白話括號裡面再嵌一個白話——插入位置錯亂嘅徵狀
      3. 同一段白話掛喺兩句唔同嘅文言引語上——今譯與原文錯配
    """
    from collections import defaultdict
    errs = []
    gloss_of = defaultdict(set)
    where = defaultdict(set)
    files = (sorted(ROOT.glob("idioms/*/*.md")) + sorted(ROOT.glob("idioms/*/profile.yaml"))
             + sorted(ROOT.glob("events/*.yaml")) + sorted(ROOT.glob("people/*.yaml")))
    for p in files:
        rel = p.relative_to(ROOT)
        flat = re.sub(r"\s+", "", p.read_text(encoding="utf-8"))
        for m in LABEL_LEAK.finditer(flat):
            errs.append(f"{rel}：正文混入段別標籤 {m.group(0)}")
        if NESTED_GLOSS.search(flat):
            errs.append(f"{rel}：白話括號內又出現白話，插入位置可能錯亂")
        for m in QUOTE_GLOSS_PAIR.finditer(flat):
            quote = m.group(1).rstrip("。！？」") + "」"
            gloss_of[m.group(2)].add(quote)
            where[m.group(2)].add(str(rel))
    for gloss, quotes in gloss_of.items():
        if len(quotes) > 1:
            errs.append(f"同一段白話配了 {len(quotes)} 句不同原文（{'、'.join(sorted(where[gloss]))}）："
                        f"「{gloss[:24]}…」")
    return errs


def main() -> int:
    # ── 先載入四層 id 空間 ──
    states = {s["id"]: s for s in load(DATA_DIR / "states.yaml")}
    sources = {s["id"]: s for s in load(DATA_DIR / "sources.yaml")}
    periods = {p["id"]: p for p in load(DATA_DIR / "periods.yaml")}

    idiom_paths = sorted(IDIOMS_DIR.glob("*/profile.yaml"))
    event_paths = sorted(EVENTS_DIR.glob("*.yaml")) if EVENTS_DIR.exists() else []
    person_paths = sorted(PEOPLE_DIR.glob("*.yaml")) if PEOPLE_DIR.exists() else []

    ids = {
        "states": set(states),
        "sources": sources,          # 傳字典，check_citations 要讀 ctext slug
        "periods": periods,
        "idioms": {p.parent.name for p in idiom_paths},
        "events": {p.stem for p in event_paths},
        "people": {p.stem for p in person_paths},
    }

    if not idiom_paths:
        print("搵唔到任何 idioms/*/profile.yaml", file=sys.stderr)
        return 1

    failed = False
    groups = [
        ("成語", idiom_paths, check_idiom),
        ("事件", event_paths, check_event),
        ("人物", person_paths, check_person),
    ]
    for label, paths, checker in groups:
        if not paths:
            continue
        print(f"── {label}（{len(paths)}）──")
        for p in paths:
            before = len(warnings)
            try:
                errors = checker(p, ids)
            except Exception as exc:                      # YAML 語法錯之類
                errors = [f"讀取失敗: {exc}"]
            rel = p.relative_to(ROOT)
            if errors:
                failed = True
                print(f"✗ {rel}")
                for e in errors:
                    print(f"    - {e}")
            else:
                print(f"✓ {rel}")
            for w in warnings[before:]:
                print(f"    ! {rel}：{w}")
        print()

    prose_errs = check_prose_integrity()
    if prose_errs:
        failed = True
        print("白話完整性檢查：")
        for e in prose_errs:
            print(f"  ✗ {e}")
        print()

    total = len(idiom_paths) + len(event_paths) + len(person_paths)
    if warnings:
        print(f"※ {len(warnings)} 項提示（文言引語未附白話今譯），唔阻擋建置。\n")
    print(f"共 {len(idiom_paths)} 條成語、{len(event_paths)} 個事件、"
          f"{len(person_paths)} 個人物（合計 {total}），"
          f"{'有錯誤，請修正。' if failed else '全部通過。'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
