# Transliterated track/zone names in the official CH_T text (EN key, CH_T original)
NAMES = [
 ("OCEAN VIEW","歐森畢伍"),("LOST PALACE","洛斯特派勒斯"),("WHALE LAGOON","魏爾盧根"),
 ("ROULETTE ROAD","盧勒特羅德"),("BINGO PARTY","賓果派蒂"),("PINBALL HIGHWAY","蘋寶亥衛"),
 ("THUNDER DECK","桑德疊克"),("DARK ARSENAL","達克阿瑟諾"),("TURBINE LOOP","圖本路波"),
 ("WISP CIRCUIT","威斯瑟奇特"),("MOTHER'S CANYON","馬德斯肯恩"),("DOCTOR'S MINE","達克特斯麥"),
 ("SAND ROAD","山德羅德"),("BOO'S HOUSE","布思豪斯"),("CLOCKWORK PYRAMID","克拉克沃克匹勒米德"),
 ("ICE MOUNTAIN","艾思蒙登"),("FROZEN JUNKYARD","弗洛森強克芽德"),("HIDDEN VOLCANO","喜登弗加諾"),
 ("MARKET STREET","瑪奇斯墜特"),("SKY ROAD","斯凱羅德"),("HAUNTED CASTLE","杭蒂凱索"),
 ("PLANET WISP","派勒那威斯"),("SEASIDE HILL","西賽希爾"),("GLACIERLAND","葛雷希爾蘭德"),
 ("CASINO PARK","卡西諾帕克"),("SANDOPOLIS","參德波利斯"),("ROOFTOP RUN","歐倫居盧夫"),
 ("FINAL FORTRESS","菲諾弗翠斯"),
]

# Proper zh-TW names. Official SEGA zh-TW where it exists: CrossWorlds (碧海風光, 輪盤公路, 黃沙長路,
# 市場大街, 天空之道, Wisp = 威斯, Boo = 幽靈, Sandopolis = 參德波利斯) and SONIC X SHADOW GENERATIONS
# (Seaside Hill = 海濱山, Planet Wisp = 派勒那威斯, Rooftop Run = 盧夫特普朗). Casino Park and Final Fortress
# follow the user's Sonic Heroes mod (賭場樂園 / 最終要塞). The rest are new translations.
NEW = {
 "歐森畢伍":"碧海風光", "洛斯特派勒斯":"失落宮殿", "魏爾盧根":"鯨魚潟湖",
 "盧勒特羅德":"輪盤公路", "賓果派蒂":"賓果派對", "蘋寶亥衛":"彈珠台公路",
 "桑德疊克":"雷霆甲板", "達克阿瑟諾":"黑暗兵工廠", "圖本路波":"渦輪迴環",
 "威斯瑟奇特":"威斯賽道", "馬德斯肯恩":"母親峽谷", "達克特斯麥":"博士礦坑",
 "山德羅德":"黃沙長路", "布思豪斯":"幽靈之家", "克拉克沃克匹勒米德":"發條金字塔",
 "艾思蒙登":"寒冰山脈", "弗洛森強克芽德":"冰封廢料場", "喜登弗加諾":"隱匿火山",
 "瑪奇斯墜特":"市場大街", "斯凱羅德":"天空之道", "杭蒂凱索":"鬧鬼古堡",
 "派勒那威斯":"派勒那威斯", "西賽希爾":"海濱山", "葛雷希爾蘭德":"冰河大地",
 "卡西諾帕克":"賭場樂園", "參德波利斯":"參德波利斯", "歐倫居盧夫":"盧夫特普朗",
 "菲諾弗翠斯":"最終要塞",
}

# A string that is only a track/zone name is shown as "中文 English" (English casing as in the
# English menus' mixed-case strings). Names inside sentences stay Chinese only.
EN = {zh: ' '.join(w.capitalize() for w in en.split(' ')) for en, zh in NAMES}
