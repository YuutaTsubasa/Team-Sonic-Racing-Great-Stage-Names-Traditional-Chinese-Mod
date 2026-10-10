# 《索尼克團隊賽車》賽道名稱正名 MOD（繁體中文）

Team Sonic Racing (PC/Steam) 的官方繁中把賽道與區域名稱寫成音譯（例如 Ocean View＝「歐森畢伍」、
Clockwork Pyramid＝「克拉克沃克匹勒米德」）。這個 MOD 只把這 28 個名稱改成正常的中文譯名，
其餘文字維持官方翻譯。

## 譯名

有 SEGA 官方繁中的一律採用：《索尼克賽車 交叉世界》（碧海風光、輪盤公路、黃沙長路、市場大街、天空之道；
Wisp＝威斯、Boo＝幽靈、Sandopolis＝參德波利斯）與《索尼克×夏特 世代》（Seaside Hill＝海濱山、
Planet Wisp＝派勒那威斯、Rooftop Run＝盧夫特普朗）。賭場樂園、最終要塞沿用《索尼克英雄》中文化的譯名，其餘為新譯。

| English | 官方繁中（音譯） | 本 MOD |
| --- | --- | --- |
| Ocean View | 歐森畢伍 | 碧海風光 |
| Lost Palace | 洛斯特派勒斯 | 失落宮殿 |
| Whale Lagoon | 魏爾盧根 | 鯨魚潟湖 |
| Roulette Road | 盧勒特羅德 | 輪盤公路 |
| Bingo Party | 賓果派蒂 | 賓果派對 |
| Pinball Highway | 蘋寶亥衛 | 彈珠台公路 |
| Thunder Deck | 桑德疊克 | 雷霆甲板 |
| Dark Arsenal | 達克阿瑟諾 | 黑暗兵工廠 |
| Turbine Loop | 圖本路波 | 渦輪迴環 |
| Wisp Circuit | 威斯瑟奇特 | 威斯賽道 |
| Mother'S Canyon | 馬德斯肯恩 | 母親峽谷 |
| Doctor'S Mine | 達克特斯麥 | 博士礦坑 |
| Sand Road | 山德羅德 | 黃沙長路 |
| Boo'S House | 布思豪斯 | 幽靈之家 |
| Clockwork Pyramid | 克拉克沃克匹勒米德 | 發條金字塔 |
| Ice Mountain | 艾思蒙登 | 寒冰山脈 |
| Frozen Junkyard | 弗洛森強克芽德 | 冰封廢料場 |
| Hidden Volcano | 喜登弗加諾 | 隱匿火山 |
| Market Street | 瑪奇斯墜特 | 市場大街 |
| Sky Road | 斯凱羅德 | 天空之道 |
| Haunted Castle | 杭蒂凱索 | 鬧鬼古堡 |
| Planet Wisp | 派勒那威斯 | 派勒那威斯 |
| Seaside Hill | 西賽希爾 | 海濱山 |
| Glacierland | 葛雷希爾蘭德 | 冰河大地 |
| Casino Park | 卡西諾帕克 | 賭場樂園 |
| Sandopolis | 參德波利斯 | 參德波利斯 |
| Rooftop Run | 歐倫居盧夫 | 盧夫特普朗 |
| Final Fortress | 菲諾弗翠斯 | 最終要塞 |

## 安裝

1. 先備份遊戲資料夾 `Team Sonic Racing/data/ui/frontend/` 中下列檔案（或日後用 Steam「驗證遊戲檔案完整性」還原）。
2. 把壓縮檔裡的 `data` 資料夾複製到 `Steam/steamapps/common/Team Sonic Racing/`，覆蓋檔案。
3. 遊戲語言選「繁體中文」。

修改 25 個 `_CH_T` 繁中檔案：賽道名稱的文字在 `CommonProjects`、`TSR_Help`、`TSR_HUD`、`TSR_Narrative`、`TSR_Options`，
但每個畫面的 `.stz` 都有自己的一份字型，所以其餘畫面檔也補了新字形。

單獨顯示賽道名的地方寫成「中文 English」（例如「碧海風光 Ocean View」）；句子裡的名稱與「…主題」只用中文。

## 技術說明（tools/）

- `.stz`：6 段 zlib 區段；第 3 段是資料 chunk（PTEX/KFRM/OBJS/SCNE/FONT/TEXT），第 4 段是每個 chunk 的 RELO 指標表。
  未修改時重建結果與原檔逐位元組相同。
- TEXT：hash → 字串指標；重建字串池即可改變長度。
- FONT：每個字型 = 字碼表 + 40 位元組字形紀錄；查表方式為 `index = (T[c % N] ^ c) % N`，`fontlib.build_table` 重新產生。
- 官方字型缺的字（丘、堡、峽、潟、濱、礦、霆、鯨 等）由 `glyphgen.py` 依各字型自己的樣式（外框、陰影、漸層）以
  Noto Sans TC 繪製，放進新增的 DXT5 貼圖頁與 sprite。
- `python tools/build.py` 讀取遊戲原檔、輸出到 `out/data/`；`python tools/verify.py` 讀回檢查並輸出預覽圖。

## 還原

原始檔備份在 `backup/data/`，複製回遊戲資料夾即可（或用 Steam 驗證檔案）。安裝後 `tools/build.py` 會從 `backup/` 讀原檔。

## 從原始碼建置

需要 Python 3.12 與 `numpy`、`pillow`、`scipy`，以及 Windows 內建的 Noto Sans TC（`C:/Windows/Fonts/NotoSansTC-VF.ttf`）。
遊戲檔只會讀取，輸出寫到 `out/`。請對未安裝本 MOD 的原版檔案建置（若 `backup/data/` 存在會優先從那裡讀原檔）；遊戲不在預設路徑時設定 `TSR_DATA` 指向遊戲的 `data` 資料夾。

```bash
pip install numpy pillow scipy
```

```bash
python tools/build.py
```

```bash
python tools/verify.py
```

`build.py` 會先替每種字型樣式擬合畫法（多核心平行，結果快取在 `work/glyphs/`），再組裝 `out/data/ui/frontend/` 下的檔案。
`verify.py` 讀回檢查：舊音譯名不再出現、原有字形都查得到、每個能顯示賽道名的字型都畫得出新名稱，並輸出 `work/verify.png` 預覽。

本儲存庫只有工具與譯名，不含任何遊戲檔案。
