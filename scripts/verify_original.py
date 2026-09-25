#!/usr/bin/env python3
"""以維基文庫原文逐字核對事件 original 各段 quote。

ctext.org 設有防抓取關卡，並明言不歡迎程式抓取，故改用維基文庫（zh.wikisource.org）的 action=raw。
維基文庫與 ctext 底本不盡相同（如《戰國策》用士禮居本），報告的差異須人手判斷：
異體字已在 VARIANT 統一；版本異文（如「未去／未至」）可保留，模型改字則須改正。

用法：
  python3 scripts/verify_original.py events/bi-zhi-zhan.yaml
  python3 scripts/verify_original.py /tmp/rewrite/*.yaml
維基文庫頁面快取於系統暫存目錄，不寫入 repo。
"""
import difflib, re, sys, tempfile, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path
import yaml

CACHE = Path(tempfile.gettempdir()) / "wikisource-cache"
CACHE.mkdir(exist_ok=True)
UA = "history-of-china-verify/0.1 (https://github.com/sclastro/history-of-china)"
PUNCT = re.compile(r"[\s，。、；：？！「」『』（）《》〈〉…—．,.;:?!()\"'·‘’“”〔〕\[\]{}|=<>/a-zA-Z0-9_　-]")
# 常見異體字，只作比對時統一，不改動稿件
VARIANT = str.maketrans("爲衆羣敎旣卽竝脩庄説甯巵冲歳撃鬬獘棬閒夸鄕捨", "為眾群教既即並修莊說寧卮沖歲擊鬥弊捲間誇鄉舍")
GONG = "隱桓莊閔僖文宣成襄昭定哀"
SHIJI = {"十二諸侯年表": "014", "六國年表": "015", "周本紀": "004", "秦本紀": "005", "秦始皇本紀": "006", "吳太伯世家": "031", "齊太公世家": "032",
         "魯周公世家": "033", "燕召公世家": "034", "宋微子世家": "038", "晉世家": "039", "楚世家": "040",
         "越王句踐世家": "041", "鄭世家": "042", "趙世家": "043", "魏世家": "044", "韓世家": "045",
         "田敬仲完世家": "046", "孔子世家": "047", "管晏列傳": "062", "老子韓非列傳": "063",
         "司馬穰苴列傳": "064", "孫子吳起列傳": "065", "伍子胥列傳": "066", "仲尼弟子列傳": "067",
         "商君列傳": "068", "蘇秦列傳": "069", "張儀列傳": "070", "樗里子甘茂列傳": "071",
         "穰侯列傳": "072", "白起王翦列傳": "073", "孟子荀卿列傳": "074", "孟嘗君列傳": "075",
         "平原君虞卿列傳": "076", "魏公子列傳": "077", "春申君列傳": "078", "范睢蔡澤列傳": "079",
         "范雎蔡澤列傳": "079", "樂毅列傳": "080", "廉頗藺相如列傳": "081", "田單列傳": "082",
         "魯仲連鄒陽列傳": "083", "屈原賈生列傳": "084", "呂不韋列傳": "085", "刺客列傳": "086",
         "李斯列傳": "087", "滑稽列傳": "126"}
BOOK = {"hanfeizi": "韓非子", "zhuangzi": "莊子", "liezi": "列子", "mengzi": "孟子", "analects": "論語",
        "lv-shi-chun-qiu": "呂氏春秋", "xunzi": "荀子", "mozi": "墨子", "shuo-yuan": "說苑",
        "xin-xu": "新序", "huainanzi": "淮南子", "yanzi-chun-qiu": "晏子春秋"}
YANZI = {"內篇諫上": "卷一", "內篇諫下": "卷二", "內篇問上": "卷三", "內篇問下": "卷四",
         "內篇雜上": "卷五", "內篇雜下": "卷六", "外篇上": "卷七", "外篇下": "卷八"}
ANALECTS = ["學而", "為政", "八佾", "里仁", "公冶長", "雍也", "述而", "泰伯", "子罕", "鄉黨", "先進",
            "顏淵", "子路", "憲問", "衛靈公", "季氏", "陽貨", "微子", "子張", "堯曰"]
GUOYU = {name: f"國語/卷{i:02d}" for i, name in enumerate(
    ["周語上", "周語中", "周語下", "魯語上", "魯語下", "齊語", "晉語一", "晉語二", "晉語三", "晉語四",
     "晉語五", "晉語六", "晉語七", "晉語八", "晉語九", "鄭語", "楚語上", "楚語下", "吳語", "越語上", "越語下"], 1)}


def fetch(title):
    f = CACHE / (title.replace("/", "__") + ".txt")
    if not f.exists():
        url = f"https://zh.wikisource.org/w/index.php?title={urllib.parse.quote(title)}&action=raw"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        for attempt in range(4):
            try:
                text = urllib.request.urlopen(req, timeout=60).read().decode(); break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None
                time.sleep(20 * (attempt + 1))
        else:
            return None
        f.write_text(text); time.sleep(3)
    return f.read_text()


def norm(s):
    s = re.sub(r"\{\{\*\|.*?\}\}", "", s, flags=re.S)   # 刪去版本註文
    s = re.sub(r"<ref[^>]*>.*?</ref>|<[^>]+>", "", s, flags=re.S)   # 刪去註腳及標籤
    return PUNCT.sub("", s).translate(VARIANT)


def locate(c, ev):
    src = c.get("source") or ev["sources"][0]["source"]
    loc = c["locus"]
    if src == "zuo-zhuan" and (m := re.match(f"([{GONG}])公", loc)):
        return f"春秋左氏傳/{m.group(1)}公"
    if src == "zhan-guo-ce" and (m := re.match(r"(.)策(.)", loc)):
        return f"戰國策 (士禮居叢書本)/{m.group(1)}/{m.group(2)}"
    if src == "shiji" and loc in SHIJI:
        return f"史記/卷{SHIJI[loc]}"
    if src == "guo-yu":
        return GUOYU.get(loc)
    if src == "yanzi-chun-qiu":
        return f"晏子春秋/{YANZI.get(loc, loc)}"
    if src == "analects":
        n = ANALECTS.index(loc) + 1 if loc in ANALECTS else 0
        return f"論語/{loc}第{'十' * (n // 10) if n < 20 else '二十'}{'一二三四五六七八九'[n % 10 - 1] if n % 10 else ''}" if n else None
    if src in BOOK:
        return f"{BOOK[src]}/{loc}"
    return None


if len(sys.argv) < 2:
    sys.exit(__doc__)
for fn in sys.argv[1:]:
    ev = yaml.safe_load(open(fn))
    print(f"=== {ev['name']}（{Path(fn).stem}）")
    for i, c in enumerate(ev.get("original") or []):
        title = locate(c, ev)
        raw = fetch(title) if title else None
        head = f"  [{i}] {c.get('speaker', '')}（{c.get('source', '')}{c['locus']}）"
        if not raw:
            print(f"{head}：維基文庫無對應頁面{('《' + title + '》') if title else ''}，須人手核對"); continue
        text = norm(raw)
        notes = []
        for seg in (norm(x) for x in re.split(r"……|…", c["quote"])):
            if not seg or seg in text:
                continue
            pos = next((text.find(k) for k in (seg[:6], seg[-6:]) if k in text), -1)
            if pos < 0:
                notes.append(f"找不到「{seg[:12]}…」"); continue
            if seg[:6] not in text:
                pos = max(0, pos - len(seg) + 6)
            win = text[pos:pos + len(seg) + 30]
            ops = [op for op in difflib.SequenceMatcher(None, seg, win, autojunk=False).get_opcodes()
                   if op[0] != "equal"]
            if ops and ops[-1][0] == "insert" and ops[-1][1] == len(seg):
                ops = ops[:-1]
            for tag, a1, a2, b1, b2 in ops:
                notes.append(f"{seg[max(0, a1-4):a1]}〔稿：{seg[a1:a2] or '—'}｜原：{win[b1:b2] or '—'}〕")
        print(f"{head}《{title}》：" + ("逐字相符" if not notes else "；".join(notes)))
