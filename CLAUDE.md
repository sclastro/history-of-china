# CLAUDE.md

本檔供 Claude Code 在此 repo 工作時參考。使用者背景與語言要求見下文「寫作規範」。

## 專案概要

「春秋戰國成語知識庫」：以四字成語為主軸，重新組織公元前 770 至前 221 年的事件、人物與概念。
每條成語分**四層考據**——本事、典源、語形定型、可信度——四者必須分開處理，不可混為一談
（原則見 `docs/design.md`，引用規範見 `docs/sources.md`）。

網站為純靜態 HTML，由 `scripts/build_site.py` 從 YAML／Markdown 生成，**生成結果連同資料一併 commit**。
Vercel 直接發佈 repo 內已 commit 的檔案，不執行任何 build step。

- 網站：<https://history-of-china-hazel.vercel.app/>
- 預設分支（Vercel 追蹤）：`claude/spring-autumn-history-site-f4tzkd`
- 早期曾用 GitHub Actions 部署 GitHub Pages，`.github/workflows/pages.yml` 已刪除，現只用 Vercel。

## 現況（2026-09-22）

七期收錄計劃全部完成：**116 條成語、62 個事件、129 個人物**，粵語音檔 116 個（約 1.7 MB）。
`validate.py` 全部通過，餘 1 項今譯提示（見「已知問題」）。
`docs/framework.md` 候選名單尚餘約 110 條未收；續補時在該檔「五、後續收錄計劃」表下方另立期次（第八期起）。

## 目錄結構

```
idioms/<id>/profile.yaml   成語結構化數據（四層考據、關聯人物事件）
idioms/<id>/<id>.md        成語論述文章
events/<id>.yaml           事件節點（單一 YAML）
people/<id>.yaml           人物節點（單一 YAML；思想家以 philosophy_ref 外連哲學家知識庫）
data/periods.yaml          七個分期（start／end 為閉區間）
data/states.yaml           列國譜系
data/sources.yaml          文獻譜系（含 ctext slug、locus_format）
schema/*-template.yaml     三種條目的欄位範本——新增條目前必讀
docs/                      design.md、sources.md、framework.md
scripts/                   validate、build_index、build_site、build_audio、check_links
assets/                    style.css、search-index.js（生成）、audio/<id>.mp3（生成）
*.html、sitemap.xml、robots.txt、404.html   全部由 build_site.py 生成，切勿手改
```

id 一律為小寫拼音、連字號分隔，檔名／目錄名即 id。年份用整數，公元前為負數（-632），約數用字串 `"c. -632"`。

## 常用指令

依賴：Python 3、PyYAML；音檔另需 `pip install gtts`（需連網）。

```sh
python3 scripts/validate.py        # 格式及交叉引用檢查；有錯誤時 exit code 非 0
python3 scripts/build_index.py     # 重生 README.md 內 <!-- INDEX:START/END --> 之間的統計與一覽
python3 scripts/build_site.py      # 重生全部 HTML、search-index.js、sitemap.xml
python3 scripts/build_audio.py     # 為新成語生成粵語音檔（--force 全部重做；--list 只列出）
python3 scripts/check_links.py     # 覆檢 ctext.org 與教育部成語典連結（需連網；403 標為「無法判定」）
```

## 修改條目的標準流程

1. 按 `schema/` 範本新增或修改 YAML／Markdown；新成語同時補相關 `events/`、`people/` 節點及 `related_idioms`。
2. 執行 `validate.py`，須全部通過；今譯提示亦應盡量清零。
3. 執行 `build_index.py`、`build_site.py`；新成語另執行 `build_audio.py`。
4. 把資料、生成的 HTML、`assets/search-index.js`、音檔、`README.md` **一併 commit**，否則線上仍是舊版。
5. 完成一期時更新 `docs/framework.md` 的收錄計劃表及本檔「現況」一節。

注意：`sitemap.xml` 的 `<lastmod>` 取建置當日日期，故每次重建都會產生 diff；若資料未變，可不 commit 此檔。

`validate.py` 檢查的交叉引用包括：`benshi.event` 須存在於 `events/`，`people[]` 須存在於 `people/`，
`states`／`period`／`dianyuan[].source` 須對應 `data/*.yaml`，`ctext_urn` 書名須與該文獻 ctext slug 一致，
`type: parable` 必須配 `reliability: 寓言`，`related_idioms[].target` 須存在且不指向自身。

## 內容規範

- **四層考據分開**：本事（史實）、典源（最早出處及段落）、定型（四字語形何時確立）、可信度（信史／大體可信／孤證／後世附會／寓言）。
- **文言一律附白話**：`dianyuan[].quote` 配 `translation` 欄；論述文章引文下方用「白話」色塊；
  敘事及小傳內的行內文言引語緊接「（白話：……）」。譯文全部自譯，不抄錄他人譯本。
- 引號「」內只放原文。轉述不可加引號，否則既誤導讀者，亦會觸發 `validate.py` 的今譯提示。
- 原文附 ctext.org 段落級連結（`ctext_urn`）；語形釋義以教育部《成語典》交叉核對，只作核對，不抄錄其文字。
- 先秦思想家的思想部分不在本站重寫，以 `philosophy_ref` 外連 <https://cc-philosophy.vercel.app/>。

## 寫作規範

使用者為香港中學教師。對使用者的回覆及一切讀者可見文字（小傳、敘事、論述、README、commit message）
一律用**繁體中文正統書面語**，不用廣東口語；中文標點用全形；技術名詞及程式碼保留英文。
用語參考陳雲《中文解讀》，避免歐化句式與冗贅虛詞。回覆簡潔直接，以段落為主。

程式碼註解及部分 schema 註解、`validate.py` 輸出仍混有廣東口語（如「唔」「嘅」），屬歷史遺留；
改動相關檔案時可順手改為書面語，但毋須為此另開 commit。

## 已知問題

- `people/ping-yuan-jun.yaml` 的 `bio` 把轉述「十步之內楚王性命就懸在他手上」置於引號內，觸發今譯提示；
  應改為不加引號的轉述，或引《史記》原文「十步之內，王不得恃楚國之眾也，王之命縣於遂手」並附白話。
- `docs/framework.md` 第三節候選名單的戰國三期小標題起訖（前 339、前 338–前 261、前 260 起）
  與 `data/periods.yaml`（前 338、前 337–前 285、前 284 起）不一致，以 `periods.yaml` 為準。
- `docs/framework.md` 末段兩句「續補時另立期次」內容重複，可刪其一。
- `README.md`「維護流程」一節仍用廣東口語，與全站書面語規範不符。
