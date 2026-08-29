# 春秋戰國成語知識庫

**網站：<https://history-of-china-hazel.vercel.app/>**
（[時間 × 列國年表](https://history-of-china-hazel.vercel.app/timeline.html)：一圖看盡五百五十年・
[成語索引](https://history-of-china-hazel.vercel.app/idioms.html)：四種分組方式・
[文獻譜系](https://history-of-china-hazel.vercel.app/sources.html)：這段歷史該查哪些書）

以**四字成語**為主軸，重新組織公元前 770 至前 221 年的歷史事件、人物與概念。

一般成語網站把「故事」與「成語」直接等同：講一個故事，末了說「後人因此有了某某成語」。
這種寫法把三件不同的事情壓成一件，讀者無從分辨哪些是史料明載、哪些是後人追加、
哪些根本是諸子編出來說理的。

本站把它們拆開，**每條成語分四層處理**：

| 層 | 問的問題 | 例：臥薪嘗膽 |
|---|---|---|
| **本事** | 歷史上實際發生了什麼？ | 前 494 年句踐敗於夫椒，前 473 年滅吳 |
| **典源** | 最早見於哪本書、哪一段？ | 《左傳》《國語》**皆無此語**；「嘗膽」首見《史記》，作「置膽於坐」 |
| **語形定型** | 四字形式何時確立？ | 「臥薪嘗膽」四字連用最早見於蘇軾，而且說的是**孫權** |
| **可信度** | 有多可信？有沒有相牴的記載？ | 大體可信——本事確鑿，「臥薪」為宋人所加 |

由本事到今日形態，這一條前後跨越兩千年。分清這四層，正是本站與成語列表的分別。

每條成語的原文都附 [ctext.org](https://ctext.org/) 的**段落級連結**，可即時覆核；
語形與釋義另以教育部《成語典》交叉核對（只作核對，不抄錄其文字）。

**文言一律附白話**：典源原文有 `translation` 欄；論述文章的引文下方是「白話」色塊；
敘事與小傳中的行內引語則緊接「（白話：……）」夾註。
`validate.py` 會提示未附今譯的文言引語。譯文全部自譯。

## 條目結構

```
idioms/<id>/profile.yaml   結構化數據：四層考據、關聯人物事件、雙欄啟示（可供程式查詢）
idioms/<id>/<id>.md        論述文章（供讀者閱讀）
events/<id>.yaml           事件節點：敘事、史料、意義
people/<id>.yaml           人物節點：小傳、生平年表、關聯
data/{states,sources,periods}.yaml   列國譜系、文獻譜系、分期定義
```

事件與人物刻意做成單一 YAML 而非資料夾——它們是把成語串起來的骨架，
成語才是主條目。詳見 [docs/design.md](docs/design.md)。

**與哲學家知識庫的分工**：先秦思想家（孔子、老子、莊子、孟子、韓非……）
的思想部分不在本站重複撰寫，`people/` 以 `philosophy_ref` 欄外連至
[哲學家知識庫](https://cc-philosophy.vercel.app/)——
那邊講他們想了什麼，這邊講他們身在什麼局裡。

## 文件

- [docs/design.md](docs/design.md) — 四層考據原則（以臥薪嘗膽、烽火戲諸侯為範例）
- [docs/sources.md](docs/sources.md) — 文獻分層與引用規範
- [docs/framework.md](docs/framework.md) — 分期架構、列國泳道、成語候選名單與分期收錄計劃
- [schema/](schema/) — 三種條目的欄位 template

## 部署

網站由 **Vercel** 部署，網址：**<https://history-of-china-hazel.vercel.app/>**

生成好的 HTML 已經連同資料一起 commit，所以 Vercel 不需要任何 build step：
Framework Preset 選 **Other**、Root Directory 用 `./`、Build Command 留空即可。
推送到本分支後 Vercel 會自動重新部署。

> **注意**：Vercel 直接發佈 repo 裡已 commit 的 HTML，並不會替你跑 `build_site.py`。
> 所以改完 `idioms/` `events/` `people/` 的 YAML 之後，**一定要在本機重跑一次
> `build_site.py` 並把生成的 HTML 一起 commit**，否則線上看到的仍是舊版。

改網址（自訂域名）：改 `scripts/build_site.py` 的 `SITE_URL`，再跑一次 `build_site.py`。
它只影響 canonical、Open Graph、`sitemap.xml`、`robots.txt`——站內連結全部是相對路徑，
換域名或放到子路徑都不用改。

## 粵語發音

每條成語旁的喇叭掣播放粵語讀音。音檔在**建置時**預先生成並存為靜態檔案
（`assets/audio/<id>.mp3`，41 個共約 520 KB），網站只負責播放：

```bash
pip install gtts
python3 scripts/build_audio.py            # 只生成尚未存在者
python3 scripts/build_audio.py --force    # 全部重做
python3 scripts/build_audio.py --list     # 只列出成語與粵拼
```

引擎為 Google Translate 的粵語 TTS（`gtts`，`lang="yue"`），免費、無須 API key。

不採用瀏覽器內置的 `speechSynthesis`，是因為粵語 voice 覆蓋率不穩：
iOS／macOS 有 Sinji、Android 一般有 Google 粵語、Windows 有 zh-HK，
但桌面 Linux 與部分 Chrome 完全沒有粵語 voice，按下去毫無反應。
亦不採用 ElevenLabs、Gemini TTS、MiniMax——前兩者官方語言表沒有粵語，
實測讀出來是普通話；MiniMax 雖聲稱支援，實測亦非地道粵語。

**新增條目後記得重跑 `build_audio.py` 並把音檔一併 commit**，
與 HTML 一樣——Vercel 只發佈 repo 裡已 commit 的檔案。

破音字：TTS 未必讀對成語中的異讀。每條成語的 `jyutping` 欄會顯示在讀音旁，
可用來核對。

## 維護流程

新增或修改條目後：

```sh
python3 scripts/validate.py        # 檢查格式與四層 id 空間嘅交叉引用
python3 scripts/build_index.py     # 重新生成本 README 索引
python3 scripts/build_site.py      # 重新生成網站頁面
```

`validate.py` 除咗檢查必填欄位，仲會檢查：
`benshi.event` 存在於 `events/`、`people[]` 全部存在於 `people/`、
`states`／`period`／`dianyuan[].source` 對得上 `data/*.yaml`、
`ctext_urn` 嘅書名同該文獻嘅 ctext slug 一致、
`type: parable` 必須配 `reliability: 寓言`、
`related_idioms[].target` 存在且唔指向自己。

**連結覆檢**：ctext.org 同教育部成語典嘅網址可能改動，舊連結會靜靜變成 404，
故宜定期執行（需連網）：

```sh
python3 scripts/check_links.py
```

> ctext.org 會擋非瀏覽器嘅 User-Agent。`check_links.py` 已帶瀏覽器 UA，
> 若仍回 403 會標為「無法判定」而唔算失敗——請人手覆核。

<!-- INDEX:START -->

## 收錄統計

目前收錄 **64** 條成語、**51** 個事件、**110** 個人物。

| 分期 | 起訖 | 成語 | 事件 |
|---|---|---:|---:|
| 平王東遷 | 前 771 – 前 723 | 1 | 1 |
| 春秋前期・鄭莊小霸 | 前 722 – 前 686 | 2 | 2 |
| 春秋中期・五霸迭興 | 前 685 – 前 547 | 26 | 22 |
| 春秋後期・吳越爭霸 | 前 546 – 前 473 | 5 | 3 |
| 戰國前期・變法圖強 | 前 472 – 前 338 | 13 | 7 |
| 戰國中期・合縱連橫 | 前 337 – 前 285 | 12 | 6 |
| 戰國後期・秦滅六國 | 前 284 – 前 221 | 5 | 10 |

| 史料可信度 | 條數 | 判準 |
|---|---:|---|
| 信史 | 24 | 同期或近期文獻互證，可繫年繫人 |
| 大體可信 | 17 | 主源可信，細節有後世增飾 |
| 孤證 | 6 | 僅一書所載，別無旁證 |
| 後世附會 | 1 | 晚出，或與早期文獻／出土材料相牴 |
| 寓言 | 16 | 諸子所設之譬喻，本無其事 |

## 各書貢獻（典源計）

| 文獻 | 層 | 條數 |
|---|:-:|---:|
| 《左傳》 | B | 25 |
| 《戰國策》 | B | 12 |
| 《史記》 | B | 9 |
| 《韓非子》 | C | 6 |
| 《莊子》 | C | 4 |
| 《列子》 | C | 3 |
| 《晏子春秋》 | C | 2 |
| 《孟子》 | C | 2 |
| 《呂氏春秋》 | C | 1 |

## 成語一覽

| 成語 | 年 | 分期 | 類型 | 典源 | 可信度 | 條目 |
|---|---|---|---|---|---|---|
| 烽火戲諸侯 | 前 771 | 平王東遷 | 史事 | 《史記》周本紀 | 後世附會 | [feng-huo-xi-zhu-hou](idioms/feng-huo-xi-zhu-hou/feng-huo-xi-zhu-hou.md) |
| 多行不義必自斃 | 前 722 | 春秋前期 | 史事 | 《左傳》隱公元年 | 信史 | [duo-xing-bu-yi](idioms/duo-xing-bu-yi/duo-xing-bu-yi.md) |
| 大義滅親 | 前 719 | 春秋前期 | 史事 | 《左傳》隱公四年 | 信史 | [da-yi-mie-qin](idioms/da-yi-mie-qin/da-yi-mie-qin.md) |
| 管鮑之交 | 前 685 | 春秋中期 | 史事 | 《史記》管晏列傳 | 大體可信 | [guan-bao-zhi-jiao](idioms/guan-bao-zhi-jiao/guan-bao-zhi-jiao.md) |
| 一鼓作氣 | 前 684 | 春秋中期 | 史事 | 《左傳》莊公十年 | 信史 | [yi-gu-zuo-qi](idioms/yi-gu-zuo-qi/yi-gu-zuo-qi.md) |
| 老馬識途 | 前 663 | 春秋中期 | 史事 | 《韓非子》說林上 | 孤證 | [lao-ma-shi-tu](idioms/lao-ma-shi-tu/lao-ma-shi-tu.md) |
| 假道伐虢 | 前 658 | 春秋中期 | 史事 | 《左傳》僖公二年 | 信史 | [jia-dao-fa-guo](idioms/jia-dao-fa-guo/jia-dao-fa-guo.md) |
| 風馬牛不相及 | 前 656 | 春秋中期 | 史事 | 《左傳》僖公四年 | 信史 | [feng-ma-niu-bu-xiang-ji](idioms/feng-ma-niu-bu-xiang-ji/feng-ma-niu-bu-xiang-ji.md) |
| 唇亡齒寒 | 前 655 | 春秋中期 | 史事 | 《左傳》僖公五年 | 信史 | [chun-wang-chi-han](idioms/chun-wang-chi-han/chun-wang-chi-han.md) |
| 外強中乾 | 前 645 | 春秋中期 | 史事 | 《左傳》僖公十五年 | 信史 | [wai-qiang-zhong-gan](idioms/wai-qiang-zhong-gan/wai-qiang-zhong-gan.md) |
| 秦晉之好 | 前 636 | 春秋中期 | 史事 | 《左傳》僖公二十三年 | 信史 | [qin-jin-zhi-hao](idioms/qin-jin-zhi-hao/qin-jin-zhi-hao.md) |
| 貪天之功 | 前 636 | 春秋中期 | 史事 | 《左傳》僖公二十四年 | 信史 | [tan-tian-zhi-gong](idioms/tan-tian-zhi-gong/tan-tian-zhi-gong.md) |
| 表裡山河 | 前 632 | 春秋中期 | 史事 | 《左傳》僖公二十八年 | 信史 | [biao-li-shan-he](idioms/biao-li-shan-he/biao-li-shan-he.md) |
| 退避三舍 | 前 632 | 春秋中期 | 史事 | 《左傳》僖公二十三年 | 信史 | [tui-bi-san-she](idioms/tui-bi-san-she/tui-bi-san-she.md) |
| 東道主 | 前 630 | 春秋中期 | 史事 | 《左傳》僖公三十年 | 信史 | [dong-dao-zhu](idioms/dong-dao-zhu/dong-dao-zhu.md) |
| 厲兵秣馬 | 前 627 | 春秋中期 | 史事 | 《左傳》僖公三十三年 | 信史 | [li-bing-mo-ma](idioms/li-bing-mo-ma/li-bing-mo-ma.md) |
| 一鳴驚人 | 前 611 | 春秋中期 | 史事 | 《韓非子》喻老 | 大體可信 | [yi-ming-jing-ren](idioms/yi-ming-jing-ren/yi-ming-jing-ren.md) |
| 各自為政 | 前 607 | 春秋中期 | 史事 | 《左傳》宣公二年 | 信史 | [ge-zi-wei-zheng](idioms/ge-zi-wei-zheng/ge-zi-wei-zheng.md) |
| 問鼎中原 | 前 606 | 春秋中期 | 史事 | 《左傳》宣公三年 | 信史 | [wen-ding-zhong-yuan](idioms/wen-ding-zhong-yuan/wen-ding-zhong-yuan.md) |
| 狼子野心 | 前 605 | 春秋中期 | 史事 | 《左傳》宣公四年 | 大體可信 | [lang-zi-ye-xin](idioms/lang-zi-ye-xin/lang-zi-ye-xin.md) |
| 篳路藍縷 | 前 597 | 春秋中期 | 史事 | 《左傳》宣公十二年 | 信史 | [bi-lu-lan-lv](idioms/bi-lu-lan-lv/bi-lu-lan-lv.md) |
| 困獸猶鬥 | 前 597 | 春秋中期 | 史事 | 《左傳》宣公十二年 | 信史 | [kun-shou-you-dou](idioms/kun-shou-you-dou/kun-shou-you-dou.md) |
| 止戈為武 | 前 597 | 春秋中期 | 史事 | 《左傳》宣公十二年 | 信史 | [zhi-ge-wei-wu](idioms/zhi-ge-wei-wu/zhi-ge-wei-wu.md) |
| 鞭長莫及 | 前 594 | 春秋中期 | 史事 | 《左傳》宣公十五年 | 信史 | [bian-chang-mo-ji](idioms/bian-chang-mo-ji/bian-chang-mo-ji.md) |
| 爾虞我詐 | 前 594 | 春秋中期 | 史事 | 《左傳》宣公十五年 | 信史 | [er-yu-wo-zha](idioms/er-yu-wo-zha/er-yu-wo-zha.md) |
| 結草報恩 | 前 594 | 春秋中期 | 史事 | 《左傳》宣公十五年 | 大體可信 | [jie-cao-bao-en](idioms/jie-cao-bao-en/jie-cao-bao-en.md) |
| 疲於奔命 | 前 584 | 春秋中期 | 史事 | 《左傳》成公七年 | 信史 | [pi-yu-ben-ming](idioms/pi-yu-ben-ming/pi-yu-ben-ming.md) |
| 病入膏肓 | 前 581 | 春秋中期 | 史事 | 《左傳》成公十年 | 大體可信 | [bing-ru-gao-huang](idioms/bing-ru-gao-huang/bing-ru-gao-huang.md) |
| 上下其手 | 前 547 | 春秋中期 | 史事 | 《左傳》襄公二十六年 | 信史 | [shang-xia-qi-shou](idioms/shang-xia-qi-shou/shang-xia-qi-shou.md) |
| 南橘北枳 | 前 531 | 春秋後期 | 史事 | 《晏子春秋》內篇雜下 | 孤證 | [nan-ju-bei-zhi](idioms/nan-ju-bei-zhi/nan-ju-bei-zhi.md) |
| 二桃殺三士 | 前 517 | 春秋後期 | 史事 | 《晏子春秋》內篇諫下 | 孤證 | [er-tao-sha-san-shi](idioms/er-tao-sha-san-shi/er-tao-sha-san-shi.md) |
| 臥薪嘗膽 | 前 490 | 春秋後期 | 史事 | 《史記》越王句踐世家 | 大體可信 | [wo-xin-chang-dan](idioms/wo-xin-chang-dan/wo-xin-chang-dan.md) |
| 鳥盡弓藏 | 前 473 | 春秋後期 | 史事 | 《史記》越王句踐世家 | 大體可信 | [niao-jin-gong-cang](idioms/niao-jin-gong-cang/niao-jin-gong-cang.md) |
| 東施效顰 | — | 春秋後期 | 寓言 | 《莊子》天運 | 寓言 | [dong-shi-xiao-pin](idioms/dong-shi-xiao-pin/dong-shi-xiao-pin.md) |
| 三家分晉 | 前 403 | 戰國前期 | 史事 | 《史記》六國年表 | 信史 | [san-jia-fen-jin](idioms/san-jia-fen-jin/san-jia-fen-jin.md) |
| 徙木立信 | 前 356 | 戰國前期 | 史事 | 《史記》商君列傳 | 大體可信 | [xi-mu-li-xin](idioms/xi-mu-li-xin/xi-mu-li-xin.md) |
| 南轅北轍 | 前 354 | 戰國前期 | 史事 | 《戰國策》魏策四 | 孤證 | [nan-yuan-bei-zhe](idioms/nan-yuan-bei-zhe/nan-yuan-bei-zhe.md) |
| 門庭若市 | 前 350 | 戰國前期 | 史事 | 《戰國策》齊策一 | 大體可信 | [men-ting-ruo-shi](idioms/men-ting-ruo-shi/men-ting-ruo-shi.md) |
| 作法自斃 | 前 338 | 戰國前期 | 史事 | 《史記》商君列傳 | 大體可信 | [zuo-fa-zi-bi](idioms/zuo-fa-zi-bi/zuo-fa-zi-bi.md) |
| 高山流水 | — | 戰國前期 | 寓言 | 《列子》湯問 | 寓言 | [gao-shan-liu-shui](idioms/gao-shan-liu-shui/gao-shan-liu-shui.md) |
| 井底之蛙 | — | 戰國前期 | 寓言 | 《莊子》秋水 | 寓言 | [jing-di-zhi-wa](idioms/jing-di-zhi-wa/jing-di-zhi-wa.md) |
| 庖丁解牛 | — | 戰國前期 | 寓言 | 《莊子》養生主 | 寓言 | [pao-ding-jie-niu](idioms/pao-ding-jie-niu/pao-ding-jie-niu.md) |
| 杞人憂天 | — | 戰國前期 | 寓言 | 《列子》天瑞 | 寓言 | [qi-ren-you-tian](idioms/qi-ren-you-tian/qi-ren-you-tian.md) |
| 五十步笑百步 | — | 戰國前期 | 寓言 | 《孟子》梁惠王上 | 寓言 | [wu-shi-bu-xiao-bai-bu](idioms/wu-shi-bu-xiao-bai-bu/wu-shi-bu-xiao-bai-bu.md) |
| 揠苗助長 | — | 戰國前期 | 寓言 | 《孟子》公孫丑上 | 寓言 | [ya-miao-zhu-zhang](idioms/ya-miao-zhu-zhang/ya-miao-zhu-zhang.md) |
| 愚公移山 | — | 戰國前期 | 寓言 | 《列子》湯問 | 寓言 | [yu-gong-yi-shan](idioms/yu-gong-yi-shan/yu-gong-yi-shan.md) |
| 朝三暮四 | — | 戰國前期 | 寓言 | 《莊子》齊物論 | 寓言 | [zhao-san-mu-si](idioms/zhao-san-mu-si/zhao-san-mu-si.md) |
| 前倨後恭 | 前 333 | 戰國中期 | 史事 | 《戰國策》秦策一 | 大體可信 | [qian-ju-hou-gong](idioms/qian-ju-hou-gong/qian-ju-hou-gong.md) |
| 畫蛇添足 | 前 323 | 戰國中期 | 史事 | 《戰國策》齊策二 | 大體可信 | [hua-she-tian-zu](idioms/hua-she-tian-zu/hua-she-tian-zu.md) |
| 千金買骨 | 前 311 | 戰國中期 | 史事 | 《戰國策》燕策一 | 大體可信 | [qian-jin-mai-gu](idioms/qian-jin-mai-gu/qian-jin-mai-gu.md) |
| 高枕無憂 | 前 295 | 戰國中期 | 史事 | 《戰國策》齊策四 | 大體可信 | [gao-zhen-wu-you](idioms/gao-zhen-wu-you/gao-zhen-wu-you.md) |
| 狡兔三窟 | 前 295 | 戰國中期 | 史事 | 《戰國策》齊策四 | 大體可信 | [jiao-tu-san-ku](idioms/jiao-tu-san-ku/jiao-tu-san-ku.md) |
| 狐假虎威 | — | 戰國中期 | 寓言 | 《戰國策》楚策一 | 寓言 | [hu-jia-hu-wei](idioms/hu-jia-hu-wei/hu-jia-hu-wei.md) |
| 諱疾忌醫 | — | 戰國中期 | 寓言 | 《韓非子》喻老 | 寓言 | [hui-ji-ji-yi](idioms/hui-ji-ji-yi/hui-ji-ji-yi.md) |
| 刻舟求劍 | — | 戰國中期 | 寓言 | 《呂氏春秋》慎大覽·察今 | 寓言 | [ke-zhou-qiu-jian](idioms/ke-zhou-qiu-jian/ke-zhou-qiu-jian.md) |
| 濫竽充數 | — | 戰國中期 | 寓言 | 《韓非子》內儲說上 | 寓言 | [lan-yu-chong-shu](idioms/lan-yu-chong-shu/lan-yu-chong-shu.md) |
| 三人成虎 | — | 戰國中期 | 寓言 | 《戰國策》魏策二 | 寓言 | [san-ren-cheng-hu](idioms/san-ren-cheng-hu/san-ren-cheng-hu.md) |
| 守株待兔 | — | 戰國中期 | 寓言 | 《韓非子》五蠹 | 寓言 | [shou-zhu-dai-tu](idioms/shou-zhu-dai-tu/shou-zhu-dai-tu.md) |
| 自相矛盾 | — | 戰國中期 | 寓言 | 《韓非子》難一 | 寓言 | [zi-xiang-mao-dun](idioms/zi-xiang-mao-dun/zi-xiang-mao-dun.md) |
| 完璧歸趙 | 前 283 | 戰國後期 | 史事 | 《史記》廉頗藺相如列傳 | 大體可信 | [wan-bi-gui-zhao](idioms/wan-bi-gui-zhao/wan-bi-gui-zhao.md) |
| 亡羊補牢 | 前 278 | 戰國後期 | 史事 | 《戰國策》楚策四 | 大體可信 | [wang-yang-bu-lao](idioms/wang-yang-bu-lao/wang-yang-bu-lao.md) |
| 鷸蚌相爭 | 前 270 | 戰國後期 | 史事 | 《戰國策》燕策二 | 孤證 | [yu-bang-xiang-zheng](idioms/yu-bang-xiang-zheng/yu-bang-xiang-zheng.md) |
| 紙上談兵 | 前 260 | 戰國後期 | 史事 | 《史記》廉頗藺相如列傳 | 信史 | [zhi-shang-tan-bing](idioms/zhi-shang-tan-bing/zhi-shang-tan-bing.md) |
| 驚弓之鳥 | 前 257 | 戰國後期 | 史事 | 《戰國策》楚策四 | 孤證 | [jing-gong-zhi-niao](idioms/jing-gong-zhi-niao/jing-gong-zhi-niao.md) |

<!-- INDEX:END -->
