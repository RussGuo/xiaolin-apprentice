#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paipan.py — 过三关 Skill 的「判定逻辑层」（确定性代码，L0–L1）

职责边界（重要）：
  本脚本只输出【结构事实】与【实验性结构启发式】——四柱/藏干/十神/神煞/
  刑冲合会/显著性画像/结构信号候选，全部带证据指针与稳定 ID。
  本脚本【不生成断语】。断语属于推理层，由 SKILL.md 规程约束现场生成。

时间口径（source_school 决策，v0.5）：**北京时间统一制**——全球出生一律按出生地
  时区换算至东八区标准时（UTC+8）后排盘，**不使用真太阳时/均时差**。
  换算方式：--tz 接受 IANA 时区名（如 America/New_York、Asia/Shanghai，自动处理
  历史夏令时，含中国 1986–1991）或数字偏移（如 -5、5.5、+09:00）。
  缺省 --tz 时，输入时间视为已是北京时间（UTC+8 标准钟）。

依赖：pip3 install "lunar_python>=1.4,<2"
"""
import argparse, json, math, re, sys, datetime

VERSION = "0.19.0"
SCHEMA = "0.4"

def fail(code, message):
    print(json.dumps({"ok": False, "schema_version": SCHEMA,
                      "error": {"code": code, "message": message}}, ensure_ascii=False))
    sys.exit(2)

try:
    from lunar_python import Solar, Lunar
except ImportError:
    fail("MISSING_DEPENDENCY", '缺少依赖 lunar_python，请先执行: pip3 install "lunar_python>=1.4,<2"')

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
GAN_WX = dict(zip(GAN, "木木火火土土金金水水"))
ZHI_WX = dict(zip(ZHI, "水土木木土火火土金金土水"))
WX = "木火土金水"
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

CANG = {
    "子": [("癸", 1.0)], "丑": [("己", 1.0), ("癸", 0.5), ("辛", 0.3)],
    "寅": [("甲", 1.0), ("丙", 0.5), ("戊", 0.3)], "卯": [("乙", 1.0)],
    "辰": [("戊", 1.0), ("乙", 0.5), ("癸", 0.3)], "巳": [("丙", 1.0), ("庚", 0.5), ("戊", 0.3)],
    "午": [("丁", 1.0), ("己", 0.5)], "未": [("己", 1.0), ("丁", 0.5), ("乙", 0.3)],
    "申": [("庚", 1.0), ("壬", 0.5), ("戊", 0.3)], "酉": [("辛", 1.0)],
    "戌": [("戊", 1.0), ("辛", 0.5), ("丁", 0.3)], "亥": [("壬", 1.0), ("甲", 0.5)],
}
LIUHE = [set("子丑"), set("寅亥"), set("卯戌"), set("辰酉"), set("巳申"), set("午未")]
# 地支暗合（藏干本气五合口径，仅三组：寅丑=甲己、卯申=乙庚、午亥=丁壬）——只用于婚恋应期标注，不参与计分
ANHE = [set("寅丑"), set("卯申"), set("午亥")]
WUHE = {"甲": "己", "己": "甲", "乙": "庚", "庚": "乙", "丙": "辛",
        "辛": "丙", "丁": "壬", "壬": "丁", "戊": "癸", "癸": "戊"}  # 天干五合
SANHE = {"水": set("申子辰"), "木": set("亥卯未"), "火": set("寅午戌"), "金": set("巳酉丑")}
SANHE_MID = {"水": "子", "木": "卯", "火": "午", "金": "酉"}
SANHUI = {"水": set("亥子丑"), "木": set("寅卯辰"), "火": set("巳午未"), "金": set("申酉戌")}  # 三会方
LIUCHONG = [set("子午"), set("丑未"), set("寅申"), set("卯酉"), set("辰戌"), set("巳亥")]
LIUHAI = [set("子未"), set("丑午"), set("寅巳"), set("卯辰"), set("申亥"), set("酉戌")]
PO = [set("子酉"), set("卯午"), set("辰丑"), set("未戌"), set("寅亥"), set("巳申")]
SANXING = [("寅巳申", "无恩之刑"), ("丑戌未", "恃势之刑")]
XING2 = [("子卯", "无礼之刑")]
ZIXING = "辰午酉亥"
MU_ZHI = {"木": "未", "火": "戌", "金": "丑", "水": "辰"}  # 土墓两说，不入检测
YANGREN = {"甲": "卯", "丙": "午", "戊": "午", "庚": "酉", "壬": "子"}  # 五阳干刃（甲丙戊庚壬）
LU = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
      "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}  # 日主禄位（戊己寄丙丁）
# 触发形态分类（v0.11，取代 v0.10 错误的"外显/内隐"二分）
# 形态决定断语句式：同一领域、同样"发生了事"，冲是一次性、伏吟是反复多次——
# 把伏吟读成"内心戏"是把传统术语现代心理学化的误译（实测：三亥伏吟年＝频繁换工作）
# v0.14 E1:trigger 分两族——**关系型**(流年支 × 原局四支的两两关系:冲/合/穿/伏吟/刑/禄刃/天克地冲)
# 与**性质型**(流年支自身属性:得根/填实空亡/补缺/补三合/入墓)。两族产量结构天然不对等:
# 一个流年支能与四支结出 6-7 条关系型,性质型再强也只有 1-3 条;score 是累加制,于是
# **关系型年永远压倒性质型年**——这与"哪一年的事更可指认"无关,是机制产物。
# 而语义特异性恰好反向:性质型说清了"这件事是什么"(得根=立身之本落地/填实=悬很久的事落地),
# 关系型只说"有事发生"(冲=有一次剧变,什么剧变全靠取象)。
# 故引擎额外输出「性质型年」清单,把"扫总榜找形态"从推理层卸下来(规程见 SKILL.md 关二纪律⑤)。
NATURE_KINDS = {"得根", "填实空亡", "补缺", "补三合", "入墓", "冲墓"}

TRIGGER_FORM = {
    "冲":       ("一次性剧变", "高", "那年X了一次——断裂、突然、不可逆"),
    "天克地冲": ("彻底反转", "高", "该宫位的人事全面重来"),
    "伏吟":     ("反复往复", "高", "同类事那年不止发生一次——换了好几回/分合数次/来回折腾"),
    "填实空亡": ("落地成实", "高", "悬了很久的事那年有了结果"),
    "补缺":     ("从无到有", "高", "这条线那年第一次真正到位"),
    "禄冲":     ("根基剧动", "高", "立身之本被动：位置、职位、身体"),
    "刃冲":     ("锋刃被激", "高", "激烈行动、冲突、伤损"),
    "冲墓":     ("解封释放", "高", "封存之物出土"),
    "得根":     ("根基到位", "高", "立身之本落了地——新环境、新位置、新身份站稳"),
    "补三合":   ("会局聚成", "中", "几条线那年拢到一起成了局——合伙、进圈、势起"),
    "补三刑":   ("纠缠拉锯", "中", "扯了很久才了结——官非、口舌、反复磨"),
    "穿":       ("渐进暗耗", "中", "被慢慢磨着、暗中受损、恩中生怨"),
    "禄穿":     ("根基暗耗", "中", "立身之本被慢慢磨"),
    "刃穿":     ("锋刃受挫", "中", "使不上劲"),
    "合":       ("绑定牵绊", "中", "被结合、被拖住、纠缠不清"),
    "禄合":     ("根基被绊", "中", "被拴住、动不了"),
    "刃合":     ("锋刃被收", "中", "劲儿被收住"),
    "自刑":     ("自我消耗", "低", "自己跟自己过不去"),
    "禄伏":     ("根基原地", "低", "原地踏步"),
    "入墓":     ("收束封存", "低", "转淡、隐退、告一段落"),
    "岁运并临": ("全局大年", "中", "与其他形态叠加定域"),
}
TIANYI = {"甲": "丑未", "戊": "丑未", "庚": "丑未", "乙": "子申", "己": "子申",
          "丙": "亥酉", "丁": "亥酉", "壬": "卯巳", "癸": "卯巳", "辛": "午寅"}
WENCHANG = {"甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
            "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯"}
KUIGANG = {"庚辰", "庚戌", "壬辰", "戊戌"}
SAN_HUO = {"申子辰": {"桃花": "酉", "驿马": "寅", "华盖": "辰"},
           "寅午戌": {"桃花": "卯", "驿马": "申", "华盖": "戌"},
           "巳酉丑": {"桃花": "午", "驿马": "亥", "华盖": "丑"},
           "亥卯未": {"桃花": "子", "驿马": "巳", "华盖": "未"}}
PILLAR_NAMES = ["年", "月", "日", "时"]
GONG_LIUQIN = {"年": "祖上/父母", "月": "父母/兄弟", "日": "自己(干)/配偶(支)", "时": "子女/晚辈"}
SHISHEN_GROUP = {"比肩": "比劫", "劫财": "比劫", "食神": "食伤", "伤官": "食伤",
                 "偏财": "财", "正财": "财", "七杀": "官杀", "正官": "官杀",
                 "偏印": "印", "正印": "印"}


def yy(c):
    if c in GAN:
        return "阳" if GAN.index(c) % 2 == 0 else "阴"
    return "阳" if ZHI.index(c) % 2 == 0 else "阴"


def shishen(day_gan, other_gan):
    dw, ow = GAN_WX[day_gan], GAN_WX[other_gan]
    same_yy = yy(day_gan) == yy(other_gan)
    if dw == ow:
        return "比肩" if same_yy else "劫财"
    if SHENG[dw] == ow:
        return "食神" if same_yy else "伤官"
    if SHENG[ow] == dw:
        return "偏印" if same_yy else "正印"
    if KE[dw] == ow:
        return "偏财" if same_yy else "正财"
    return "七杀" if same_yy else "正官"


def wushu_time_gan(day_gan, time_zhi):
    """五鼠遁：由日干推时干，保证与所采用的日柱口径一致（修复 C-01）"""
    return GAN[(GAN.index(day_gan) % 5 * 2 + ZHI.index(time_zhi)) % 10]


YUE_ZHI = "寅卯辰巳午未申酉戌亥子丑"  # 节气月序（立春起寅月）


def wuhu_month_pillars(year_gan):
    """五虎遁：由流年干推 12 个流月干支（寅月起）。甲己丙寅/乙庚戊寅/丙辛庚寅/丁壬壬寅/戊癸甲寅"""
    start = (GAN.index(year_gan) % 5 * 2 + 2) % 10
    return [(GAN[(start + i) % 10], YUE_ZHI[i]) for i in range(12)]


def yuexi_of(lg, lz, zhis, zhi_set, involved, day_gan):
    """v0.19 月析（判定层）：该流年 12 流月的引动分布，输出摘要不出原始行。
    引动判据（保守三条）：①月支冲/合/伏吟岁君（月引动年）；②年月与原局三方成局/成刑；
    ③月支再冲流年已引动的原局支。口径：流月只作引动/分布证据，不独立应事（source_school）。"""
    yin, m_line = [], {}
    inv_zhis = {zhis[i] for i in involved}
    for mg, mz in wuhu_month_pillars(lg):
        hit = ({mz, lz} in LIUCHONG or {mz, lz} in LIUHE or mz == lz)
        if not hit:
            for _w5, trio in SANHE.items():
                if mz in trio and lz in trio and mz != lz and (trio - {mz, lz}) <= zhi_set:
                    hit = True; break
        if not hit:
            for combo, _nm in SANXING:
                cs = set(combo)
                if mz in cs and lz in cs and mz != lz and (cs - {mz, lz}) <= zhi_set:
                    hit = True; break
        if not hit:
            hit = any({mz, z} in LIUCHONG for z in inv_zhis)
        if hit:
            yin.append(mz)
            grp = SHISHEN_GROUP[shishen(day_gan, mg)]
            m_line[grp] = m_line.get(grp, 0) + 1
    if not yin:
        return None
    pos = [YUE_ZHI.index(m) for m in yin]
    seg = [sum(1 for p in pos if p <= 3), sum(1 for p in pos if 4 <= p <= 7), sum(1 for p in pos if p >= 8)]
    seg_name = ["前段(寅-巳,约2-6月)", "中段(午-酉,约6-10月)", "后段(戌-丑,约10-次年1月)"]
    late = sum(1 for p in pos if p >= 10)  # 子丑月＝公历12月-次年1月
    clusters = 1 + sum(1 for a, b in zip(sorted(pos), sorted(pos)[1:]) if b - a > 1)
    return {"引动月支": yin, "簇数": clusters,
            "聚集段": seg_name[max(range(3), key=lambda i: seg[i])],
            "跨立春风险": ("高" if yin and late * 2 >= len(yin) else "低"),
            "月干线索": "、".join(f"{k}×{v}" for k, v in sorted(m_line.items(), key=lambda x: -x[1])[:2])}


def triad_of(zhi):
    for k in SAN_HUO:
        if zhi in k:
            return k
    return None


def kongwang(day_gz):
    i, j = GAN.index(day_gz[0]), ZHI.index(day_gz[1])
    idx = next(n for n in range(60) if n % 10 == i and n % 12 == j)
    start = (idx // 10 * 10) % 12
    return ZHI[(start + 10) % 12] + ZHI[(start + 11) % 12]


BJT = datetime.timezone(datetime.timedelta(hours=8))  # 东八区标准时（固定 +8，不含任何夏令时）
TZ_NUM_RE = re.compile(r"^([+-]?)(\d{1,2})(?::([0-5]\d))?$")


def parse_tz(s):
    """解析 --tz：IANA 名（含'/'）或数字偏移（-5 / 5.5 / +09:00）。返回 tzinfo。"""
    if s is None:
        return None
    s = s.strip()
    if "/" in s:
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(s)
        except Exception:
            fail("INVALID_TZ", f"无法识别的 IANA 时区名: {s}")
    m = TZ_NUM_RE.match(s)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        hours = int(m.group(2)) + (int(m.group(3)) / 60 if m.group(3) else 0)
        if hours > 14:
            fail("INVALID_TZ", f"时区偏移越界: {s}")
        return datetime.timezone(datetime.timedelta(hours=sign * hours))
    try:
        hours = float(s)
        if abs(hours) > 14:
            fail("INVALID_TZ", f"时区偏移越界: {s}")
        return datetime.timezone(datetime.timedelta(hours=hours))
    except ValueError:
        fail("INVALID_TZ", f"--tz 需为 IANA 时区名或数字偏移（如 America/New_York、-5、5.5、+09:00），收到: {s}")


def to_beijing(y, m, d, hh, mm, tz):
    """按北京时间统一制换算：出生地时区 → UTC+8 标准时。返回 (naive北京时间, 跨日, 描述)。"""
    t0 = datetime.datetime(y, m, d, hh, mm)
    if tz is None:
        return t0, False, "输入即北京时间（UTC+8 标准钟）"
    t1 = t0.replace(tzinfo=tz).astimezone(BJT).replace(tzinfo=None)
    desc = f"出生地时区 {getattr(tz, 'key', str(tz))} → 北京时间"
    return t1, t1.date() != t0.date(), desc


def build_chart(y, m, d, hh, mm, sect):
    solar = Solar.fromYmdHms(y, m, d, hh, mm, 0)
    lunar = solar.getLunar()
    ec = lunar.getEightChar()
    ec.setSect(sect)
    pillars = [ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()]
    day_gan = pillars[2][0]
    # C-01 修复：时干统一由（sect 口径下的）日干经五鼠遁重算，保证四柱内部一致
    tz = pillars[3][1]
    pillars[3] = wushu_time_gan(day_gan, tz) + tz

    detail = []
    for pos, gz in enumerate(pillars):
        g, z = gz[0], gz[1]
        hidden = [{"gan": hg, "weight": w, "shishen": shishen(day_gan, hg)} for hg, w in CANG[z]]
        detail.append({
            "柱": PILLAR_NAMES[pos], "干支": gz,
            "干": g, "干五行": GAN_WX[g], "干阴阳": yy(g),
            "干十神": ("日主" if pos == 2 else shishen(day_gan, g)),
            "支": z, "支五行": ZHI_WX[z], "支阴阳": yy(z),
            "藏干": hidden, "支本气十神": shishen(day_gan, CANG[z][0][0]),
            "宫位六亲": GONG_LIUQIN[PILLAR_NAMES[pos]],
        })

    zhis = [p[1] for p in pillars]
    gans = [p[0] for p in pillars]

    # 刑冲合会（纯结构事实＋稳定 ID；断语性解释一律不出现在本层——H-07）
    inter = []
    def pname(i):
        return PILLAR_NAMES[i] + "支" + zhis[i]
    def add(t, pair, note=None, adj=None):
        item = {"id": f"REL-{len(inter)+1:02d}", "type": t, "pair": pair}
        if note:
            item["note"] = note
        if adj is not None:
            item["相邻"] = adj
        inter.append(item)
    for i in range(4):
        for j in range(i + 1, 4):
            pair = {zhis[i], zhis[j]}
            loc = f"{pname(i)}×{pname(j)}"
            if pair in LIUCHONG:
                add("六冲", loc, adj=(j - i == 1))
            if pair in LIUHE:
                add("六合", loc, adj=(j - i == 1))
            if pair in LIUHAI:
                add("六害(穿)", loc, adj=(j - i == 1))
            if pair in PO:
                add("相破", loc, adj=(j - i == 1))
            if len(pair) == 2:
                for combo, nm in XING2:
                    if pair == set(combo):
                        add("相刑", loc, note=nm)
            if zhis[i] == zhis[j]:
                if zhis[i] in ZIXING:
                    add("自刑", loc)
                add("伏吟", loc)
    for combo, nm in SANXING:
        have = [z for z in set(combo) if z in zhis]
        if len(have) == 3:
            add("三刑全", "".join(sorted(have)), note=nm)
        elif len(have) == 2:
            add("三刑缺一", "".join(sorted(have)), note=f"{nm}，缺{(set(combo)-set(have)).pop()}")
    for wx5, s in SANHE.items():
        have = [z for z in s if z in zhis]
        if len(set(have)) == 3:
            add("三合局", "".join(sorted(set(have))), note=f"合{wx5}局（成化条件未判，推理层核）")
        elif len(set(have)) == 2 and SANHE_MID[wx5] in have:
            add("半合", "".join(sorted(set(have))), note=f"拱{wx5}（含中神）")
    for wx5, mz in MU_ZHI.items():
        if mz in zhis:
            stars = [g for g in gans if GAN_WX[g] == wx5]
            if stars:
                add("墓库", f"{mz}为{wx5}之墓", note=f"天干{'、'.join(stars)}（{wx5}）见墓支")
    tkdc = [f"{PILLAR_NAMES[i]}柱{pillars[i]}×{PILLAR_NAMES[j]}柱{pillars[j]}"
            for i in range(4) for j in range(i + 1, 4)
            if {zhis[i], zhis[j]} in LIUCHONG
            and (KE[GAN_WX[gans[i]]] == GAN_WX[gans[j]] or KE[GAN_WX[gans[j]]] == GAN_WX[gans[i]])]
    if tkdc:
        add("天克地冲", "；".join(tkdc))

    # 神煞（M-02：允许基准支自身；按 (name, at) 去重合并查法）
    raw_ss = []
    kw = kongwang(pillars[2])
    for i, z in enumerate(zhis):
        if z in kw and i != 2:
            raw_ss.append(("空亡", f"{PILLAR_NAMES[i]}支{z}", f"日柱{pillars[2]}旬空{kw}"))
        if YANGREN.get(day_gan) == z:
            raw_ss.append(("阳刃", f"{PILLAR_NAMES[i]}支{z}", f"日干{day_gan}刃在{z}（五阳干刃口径）"))
        if day_gan in TIANYI and z in TIANYI[day_gan]:
            raw_ss.append(("天乙贵人", f"{PILLAR_NAMES[i]}支{z}", "以日干查"))
        if WENCHANG.get(day_gan) == z:
            raw_ss.append(("文昌", f"{PILLAR_NAMES[i]}支{z}", "以日干查"))
    for base_name, base_zhi in [("年支", zhis[0]), ("日支", zhis[2])]:
        tri = triad_of(base_zhi)
        if tri:
            for sname, target in SAN_HUO[tri].items():
                for i, z in enumerate(zhis):
                    if z == target:
                        raw_ss.append((sname, f"{PILLAR_NAMES[i]}支{z}", f"以{base_name}{base_zhi}（{tri}局）查"))
    if pillars[2] in KUIGANG:
        raw_ss.append(("魁罡", f"日柱{pillars[2]}", "庚辰庚戌壬辰戊戌"))
    ss_map = {}
    for name, at, rule in raw_ss:
        ss_map.setdefault((name, at), []).append(rule)
    shensha = [{"name": k[0], "at": k[1], "rules": sorted(set(v))} for k, v in ss_map.items()]

    # ---- L1a 旺衰（实验性启发式；H-03：去从格候选、去数值置信度、月令不重复计根）----
    dw = GAN_WX[day_gan]
    score, ev = 0.0, []
    mz_wx = ZHI_WX[zhis[1]]
    if mz_wx == dw:
        score += 3; ev.append(f"得令：月支{zhis[1]}({mz_wx})与日主同气 +3")
    elif SHENG[mz_wx] == dw:
        score += 2; ev.append(f"得令：月支{zhis[1]}({mz_wx})生日主 +2")
    for i, z in enumerate(zhis):
        if i == 1:
            continue  # 月令已计入得令，不重复计根
        for hg, w in CANG[z]:
            if GAN_WX[hg] == dw:
                pts = {1.0: 1.5, 0.5: 0.8, 0.3: 0.4}[w]
                score += pts
                ev.append(f"得地：{PILLAR_NAMES[i]}支{z}藏{hg}(同气,{'本' if w==1.0 else '中' if w==0.5 else '余'}气) +{pts}")
            elif SHENG[GAN_WX[hg]] == dw and w == 1.0:
                score += 0.6; ev.append(f"得地：{PILLAR_NAMES[i]}支{z}藏{hg}(印根) +0.6")
    for i, g in enumerate(gans):
        if i == 2:
            continue
        if GAN_WX[g] == dw:
            score += 1.0; ev.append(f"得势：{PILLAR_NAMES[i]}干{g}比劫 +1.0")
        elif SHENG[GAN_WX[g]] == dw:
            score += 0.8; ev.append(f"得势：{PILLAR_NAMES[i]}干{g}印星 +0.8")
    if score >= 5.5:
        verdict = "身旺"
    elif score >= 3.5:
        verdict = "中和偏旺"
    elif score >= 2.2:
        verdict = "中和偏弱"
    else:
        verdict = "身弱"
    wangshuai = {"verdict": verdict, "score": round(score, 2),
                 "nature": "experimental_heuristic（只计生扶不计克泄耗，无校准数据；仅供推理层参考，不得当作概率）",
                 "evidence": ev,
                 "source_school": "子平简化（参考陈素庵根印法）；盲派弃旺衰看做功——两线并存，推理层需声明采用哪线"}
    # v0.12 从格嫌疑护栏（口传 2026-07：复杂命格按常规喜忌断"甚至完全是反的"——
    # 应期强度分不经喜忌可留；旺衰→喜忌→方向判定这一段在特殊格局下整体不可靠，须降档）
    sheng_fu = ke_xie_hao = 0.0
    for z in zhis:
        for hg, w in CANG[z]:
            if SHISHEN_GROUP[shishen(day_gan, hg)] in ("比劫", "印"):
                sheng_fu += w
            else:
                ke_xie_hao += w
    for i, g in enumerate(gans):
        if i == 2:
            continue
        if SHISHEN_GROUP[shishen(day_gan, g)] in ("比劫", "印"):
            sheng_fu += 1.0
        else:
            ke_xie_hao += 1.0
    cong_flag = None
    if sheng_fu <= 0.5:
        cong_flag = f"从弱嫌疑：印比生扶总权重仅{round(sheng_fu, 1)}（日主近乎无根无助）"
    elif ke_xie_hao <= 0.5:
        cong_flag = f"从强嫌疑：克泄耗总权重仅{round(ke_xie_hao, 1)}（全局几乎尽是生扶）"
    if cong_flag:
        wangshuai["从格嫌疑"] = cong_flag
        wangshuai["护栏"] = ("特殊格局下常规旺衰喜忌可能整体反转：verdict 不可用；"
                           "方向类（散/成等喜忌依赖）判定一律降档，改用不依赖喜忌的形态断与结构断（SKILL Step2/自检）")

    # ---- L1b 十神统计与显著性（H-05：全字计数＋两级空缺）----
    ss_count = {}
    for i in range(4):
        if i != 2:
            k = shishen(day_gan, gans[i])
            ss_count[k] = ss_count.get(k, 0) + 1
        k = shishen(day_gan, CANG[zhis[i]][0][0])
        ss_count[k] = ss_count.get(k, 0) + 1
    grp_visible = {}
    for k, v in ss_count.items():
        grp_visible[SHISHEN_GROUP[k]] = grp_visible.get(SHISHEN_GROUP[k], 0) + v
    all_hidden_groups = set()
    for i in range(4):
        if i != 2:
            all_hidden_groups.add(SHISHEN_GROUP[shishen(day_gan, gans[i])])
        for hg, _w in CANG[zhis[i]]:
            all_hidden_groups.add(SHISHEN_GROUP[shishen(day_gan, hg)])
    groups = ["比劫", "食伤", "财", "官杀", "印"]
    missing_visible = [g for g in groups if grp_visible.get(g, 0) == 0]
    missing_full = [g for g in groups if g not in all_hidden_groups]

    wx_w = {w: 0.0 for w in WX}
    for g in gans:
        wx_w[GAN_WX[g]] += 1.0
    for z in zhis:
        for hg, w in CANG[z]:
            wx_w[GAN_WX[hg]] += w
    tot = sum(wx_w.values())
    probs = [v / tot for v in wx_w.values() if v > 0]
    entropy = -sum(p * math.log(p) for p in probs) / math.log(5)
    dom = max(wx_w, key=wx_w.get)
    special = []
    if len(set(gans)) == 1:
        special.append("天干一气")
    if len(set(zhis)) == 1:
        special.append("地支一气")
    if all(yy(c) == "阳" for c in gans + zhis):
        special.append("八字纯阳")
    if all(yy(c) == "阴" for c in gans + zhis):
        special.append("八字纯阴")
    strong_ids = sorted({x["id"] for x in inter if x["type"] in ("六冲", "三刑全", "六害(穿)", "天克地冲")})
    sal_score = (1 - entropy) * 3 + sum(1.2 for v in ss_count.values() if v >= 3) \
        + len(missing_visible) * 0.8 + len(strong_ids) * 0.7 + len(special) * 1.5
    saliency = {
        "五行分布(经验权重,非占比)": {k: round(v, 1) for k, v in wx_w.items()},
        "五行熵(0-1,越低越偏枯)": round(entropy, 3),
        "最旺五行": f"{dom}({round(wx_w[dom]/tot*100)}%)",
        "十神计数(干+支本气)": ss_count,
        "十神重复≥3": [k for k, v in ss_count.items() if v >= 3],
        "十神类不显(干+支本气层)": missing_visible,
        "十神类全缺(含全部藏干)": missing_full,
        "强作用REL": strong_ids,
        "特殊结构": special,
        "显著性总评": {"score": round(sal_score, 2),
                  "nature": "experimental_heuristic（阈值无回测依据，仅供选题排序参考）"},
    }

    # ---- L1c 结构信号候选（H-04：精确十神＋修复同柱检测；一律标"候选"）----
    signals = []
    gs = [None if i == 2 else shishen(day_gan, gans[i]) for i in range(4)]
    zs = [shishen(day_gan, CANG[zhis[i]][0][0]) for i in range(4)]
    def find_exact(a_names, b_names):
        """a、b 为十神名集合；返回相邻干-干 与 同柱干-支 的命中证据"""
        hits = []
        for i in range(4):
            for j in range(4):
                if i != j and abs(i - j) == 1 and gs[i] in a_names and gs[j] in b_names:
                    hits.append(f"{PILLAR_NAMES[i]}干{gans[i]}({gs[i]})贴{PILLAR_NAMES[j]}干{gans[j]}({gs[j]})")
            if gs[i] in a_names and zs[i] in b_names:
                hits.append(f"{PILLAR_NAMES[i]}柱{pillars[i]}干支自组({gs[i]}坐{zs[i]})")
            if zs[i] in a_names and gs[i] in b_names:
                hits.append(f"{PILLAR_NAMES[i]}柱{pillars[i]}干支自组({gs[i]}坐{zs[i]})")
        return sorted(set(hits))
    def sig(sid, name, hits, caveat=None):
        if hits:
            s = {"id": sid, "name": name, "evidence": hits,
                 "nature": "candidate（仅邻接/同柱结构事实；强弱、喜忌、通关未判，成立与否由推理层复核）"}
            if caveat:
                s["caveat"] = caveat
            signals.append(s)
    BIJIE, CAI = {"比肩", "劫财"}, {"偏财", "正财"}
    sig("SIG-BJDC", "比劫夺财（候选）", find_exact(BIJIE, CAI) + find_exact(CAI, BIJIE))
    sig("SIG-SGJG", "伤官见官（候选，严格伤官×正官）", find_exact({"伤官"}, {"正官"}) + find_exact({"正官"}, {"伤官"}))
    sig("SIG-SSZS", "食神近杀（候选，食神×七杀——可能为制杀结构）", find_exact({"食神"}, {"七杀"}) + find_exact({"七杀"}, {"食神"}))
    sig("SIG-XSDS", "枭神夺食（候选，严格偏印×食神）", find_exact({"偏印"}, {"食神"}) + find_exact({"食神"}, {"偏印"}))
    sig("SIG-CXPY", "财星破印（候选）", find_exact(CAI, {"正印", "偏印"}) + find_exact({"正印", "偏印"}, CAI))
    ga = [g for g in gs if g]
    if "正官" in ga and "七杀" in ga:
        sig("SIG-GSHZ", "官杀混杂（候选，干透正官又透七杀）", [f"天干见{'、'.join([g for g in ga if g in ('正官','七杀')])}"])
    signals.append({"id": "SIG-RIZUO", "name": f"日坐{zs[2]}",
                    "evidence": [f"日支{zhis[2]}本气{CANG[zhis[2]][0][0]}为{zs[2]}（配偶宫）"],
                    "nature": "fact"})
    for s in shensha:
        if s["name"] == "驿马":
            mz = s["at"][-1]
            for x in inter:
                if x["type"] == "六冲" and mz in x["pair"]:
                    sig("SIG-YMFC", "驿马逢冲（候选）", [s["at"], x["id"] + ":" + x["pair"]])
        if s["name"] == "阳刃":
            rz = s["at"][-1]
            for x in inter:
                if x["type"] == "六冲" and rz in x["pair"]:
                    sig("SIG-RENCH", "阳刃逢冲（候选）", [s["at"], x["id"] + ":" + x["pair"]])
            if {zhis[3], rz} in LIUHE:
                sig("SIG-SHIREN", "子息宫与刃合（候选）", [f"时支{zhis[3]}合{s['at']}"])
    if grp_visible.get("印", 0) >= 3:
        sig("SIG-YINZH", "印重（候选）", [f"印星干+支本气共{grp_visible['印']}见"])
    if grp_visible.get("财", 0) >= 3 and verdict in ("身弱", "中和偏弱"):
        sig("SIG-CDSR", "财多身弱（候选，依赖实验性旺衰）", [f"财星{grp_visible['财']}见且旺衰启发式={verdict}"])
    for miss in missing_visible:
        level = "full_absence" if miss in missing_full else "visible_absence"
        nm = f"十神全缺（含全部藏干）：无{miss}" if level == "full_absence" else f"十神不显（干与支本气层）：无{miss}"
        signals.append({"id": f"SIG-MISS-{miss}", "name": nm, "level": level,
                        "evidence": ["全局扫描：干、支本气" + ("、藏干中余气均不见" if level == "full_absence" else "不见（藏干中余气仍有，见 detail）")],
                        "nature": "fact",
                        "caveat": "不显≠功能缺失；仅 full_absence 可作'空缺'取象，且不得单独充当两条独立证据之一"})

    # v0.12 性格三要素基底（口传保底公式：性格＝日元＋坐下＋月令三部分十神合成一句话画像；
    # 本层只出结构事实，画像断语由推理层按象义层§5 生成）
    character_basis = {
        "日元": f"{day_gan}（{GAN_WX[day_gan]}·{yy(day_gan)}）",
        "坐下(日支)": {"支": zhis[2], "本气十神": zs[2],
                     "全部藏干": [f"{hg}={shishen(day_gan, hg)}" for hg, _w in CANG[zhis[2]]]},
        "月令(月支)": {"支": zhis[1], "本气十神": zs[1],
                     "全部藏干": [f"{hg}={shishen(day_gan, hg)}" for hg, _w in CANG[zhis[1]]]},
        "note": "口传保底公式（2026-07）：三部十神合成一句尽量短的画像——降级链的性格保底位取材处（SKILL Step3）",
    }

    return {"pillars": pillars, "day_master": f"{day_gan}({GAN_WX[day_gan]})",
            "lunar": lunar.toString(), "kongwang": kw, "detail": detail,
            "interactions": inter, "shensha": shensha,
            "L1_wangshuai": wangshuai, "L1_saliency": saliency, "signals": signals,
            "L1_character_basis": character_basis, "ec": ec}


def dayun_block(ec, gender_int, birth_year, as_of, day_gan):
    yun = ec.getYun(gender_int)
    try:
        start_solar_year = yun.getStartSolar().getYear()
    except Exception:
        try:
            start_solar_year = yun.getStartSolarYear()
        except Exception:
            start_solar_year = birth_year + yun.getStartYear()
    out = {"起运": f"出生后{yun.getStartYear()}年{yun.getStartMonth()}个月{yun.getStartDay()}天",
           "起运公历年": start_solar_year, "大运": [],
           "少年段_note": "口传 2026-07：前两步大运事关少年时期，无论命主现龄均已走过、可作过去验证——"
                        "十神×身强弱的读法见象义层§9（断语由推理层生成）"}
    ref_y = as_of.year
    current = None
    n_yun = 0
    for dy in yun.getDaYun():
        gz = dy.getGanZhi()
        if not gz:
            continue
        n_yun += 1
        item = {"干支": gz, "干十神": shishen(day_gan, gz[0]),
                "支本气十神": shishen(day_gan, CANG[gz[1]][0][0]),
                "起于公历": dy.getStartYear(), "止于": dy.getEndYear(),
                "起于虚龄": dy.getStartAge()}
        if n_yun <= 2:
            item["少年段"] = True
        if dy.getStartYear() <= ref_y <= dy.getEndYear():
            item["当前大运(按as_of)"] = True
            current = dy
        out["大运"].append(item)
    if current:
        out["当前大运流年"] = [{"年": ln.getYear(), "干支": ln.getGanZhi(), "虚龄": ln.getAge()}
                          for ln in current.getLiuNian() if abs(ln.getYear() - ref_y) <= 4]
    return out


def liu_nian_gz(year):
    """公历年 → 流年干支（1984=甲子锚点）。
    注意：干支年以立春为界——公历 1/1 至立春前仍属上一干支年。
    本函数按公历年给出，跨界修正见 mark 的 `跨年提示` 字段（v0.9）。"""
    return GAN[(year - 4) % 10] + ZHI[(year - 4) % 12]


def _wx_palaces(zhis, gans, wx5):
    """原局中该五行**当家**的柱序号(v0.14 E2 入墓/冲墓定位)。

    只认天干本身与地支**本气**(藏干第一位)——若把藏干余气也算进来,一个五行能命中三四个宫,
    "涉及宫位"就退化成"全都涉及",等于没有定位;宫位分组每宫仅 3 席,宁精勿滥。
    """
    out = set()
    for i, z in enumerate(zhis):
        if GAN_WX.get(gans[i]) == wx5 or GAN_WX[CANG[z][0][0]] == wx5:
            out.add(i)
    return out


def _diverse(rank, n=8, per_form=3, nature_quota=2):
    """v0.14 E4+:可指认榜的两条结构配额——同形态至多 per_form 席、**性质型年保底 nature_quota 席**。

    为什么要保底席位(2026-07-30 端到端实测得出):
    榜单原本纯按可指认分截断,8 席被 3 种关系型形态占满(一种独占 4 席),性质型年 0 席。
    第一版只做了"同形态限额",但性质型年之间也要排队——实测 2018(3.8)仍被同形态的 2023 挤掉。
    而**模型只查规程点名的榜**:真实对话里它明说"这是可指认榜上排第一的年份",
    对新增的『性质型年』清单看都没看。所以让它"能看见"的唯一可靠办法,是把年份放进它已经在看的地方。

    配额不是权重:不改任何一年的分数,只保证候选池里有"事件类型自明"那一类的代表。
    替换从榜尾的关系型年开始(榜首的权威不动),替换后按可指认分重排,榜仍是有序的。
    """
    out, cnt, taken = [], {}, set()
    for m in rank:
        f = m.get("主形态", "")
        if cnt.get(f, 0) >= per_form:
            continue
        out.append(m); cnt[f] = cnt.get(f, 0) + 1; taken.add(m["year"])
        if len(out) >= n:
            break
    if len(out) < n:   # 配额筛完不足 n 席:按原序补齐,不浪费席位
        for m in rank:
            if m["year"] not in taken:
                out.append(m); taken.add(m["year"])
                if len(out) >= n:
                    break
    nature_all = [m for m in rank if m.get("形态族") == "性质型"]
    need = min(nature_quota, len(nature_all)) - sum(1 for m in out if m.get("形态族") == "性质型")
    for c in [m for m in nature_all if m["year"] not in taken][:max(0, need)]:
        for i in range(len(out) - 1, -1, -1):      # 从榜尾换出关系型年
            if out[i].get("形态族") == "关系型":
                taken.discard(out[i]["year"]); out[i] = c; taken.add(c["year"]); break
    return sorted(out, key=lambda m: (-m["可指认分"], m["year"]))


def yingqi_scan(pillars, day_gan, kongwang_str, dayun_list, birth_year, as_of_year, gender=None):
    """应期扫描（L1d，experimental_heuristic）：逐年检测流年对原局的触发。
    只扫出生次年至 as_of 当年（红线：未来点状年份不输出）。
    v0.10 四项改进：①禄/刃被引动维度；②同支重复加成递减（治分数通胀）；
    ③触发标注外显/内隐（外显＝可指认的外部行动，内隐＝内在胶着）；
    ④取消 top-10 硬截断，改为总榜＋按宫位分组＋外显榜三路输出。
    v0.12：婚恋应期通道（口传四规则机械化：配偶宫填实/见合[含暗合]、男财女官年、
    鸳鸯合、冲开原局合、三刑挡道）——**纯标注不计分**，score 体系不动；另出近三年速览。
    输出为【应期候选标记】，不是事件断言。"""
    zhis = [p[1] for p in pillars]
    gans = [p[0] for p in pillars]
    lu_zhi = LU.get(day_gan)
    ren_zhi = YANGREN.get(day_gan)
    sanxing_partial = []
    for combo, nm in SANXING:
        have = [z for z in set(combo) if z in zhis]
        if len(have) == 2:
            sanxing_partial.append(((set(combo) - set(have)).pop(), nm, "".join(sorted(have))))
    wx_present = {GAN_WX[g] for g in gans} | {GAN_WX[CANG[z][0][0]] for z in zhis}
    # v0.13（Case#1 修复）D2/D3 原局准备：
    # 日主本气根缺口（四支本气层无日主五行 → 流年本气根到位＝"虚根得实"，与填实空亡同一哲学）；
    # 三合/三会用的支集合
    dw_scan = GAN_WX[day_gan]
    day_root_missing = dw_scan not in {GAN_WX[CANG[z][0][0]] for z in zhis}
    zhi_set = set(zhis)

    def dayun_of(yr):
        for dy in dayun_list:
            if dy.get("起于公历") and dy["起于公历"] <= yr <= dy["止于"]:
                return dy["干支"]
        return None

    # 虚则待实：原局全缺/不显之星被流年干补上——"明干无时暗中求"的应期面
    all_ss_present, vis_group, full_group = set(), set(), set()
    for i in range(4):
        if i != 2:
            ss0 = shishen(day_gan, gans[i])
            all_ss_present.add(ss0); vis_group.add(SHISHEN_GROUP[ss0]); full_group.add(SHISHEN_GROUP[ss0])
        for k, (hg, _w) in enumerate(CANG[zhis[i]]):
            ss0 = shishen(day_gan, hg)
            all_ss_present.add(ss0); full_group.add(SHISHEN_GROUP[ss0])
            if k == 0:
                vis_group.add(SHISHEN_GROUP[ss0])

    # v0.12 婚恋应期通道的原局准备（口传四规则）
    ri_zhi = zhis[2]
    natal_he_partners = sorted(
        {z for z in zhis if z != ri_zhi and {ri_zhi, z} in LIUHE} |
        {z for z in zhis if z != ri_zhi and any(ri_zhi in t and z in t for t in SANHE.values())})
    sanxing_full_list = [(combo, nm) for combo, nm in SANXING if all(c in zhis for c in combo)]
    hunlian_years = []

    marks = []
    fill_marks = []
    for yr in range(birth_year + 1, as_of_year + 1):
        gz = liu_nian_gz(yr)
        lg, lz = gz[0], gz[1]
        ev = []          # (描述, 权重, 类型kind, 去重键)
        # v0.14 E2:宫位集合拆两个——involved 只装"关系型"(流年支 × 原局支的两两关系),
        # 它参与下方大运共振判定(命中 ×1.4),语义与旧版逐字节一致,**绝不能因本次改动变大**;
        # involved_view 额外装"性质型"(得根/入墓/填实/补缺/补局——流年支自身属性),
        # 只用于「涉及宫位」输出与「按宫位分组」,不参与任何计分。
        # 不合并的理由:大运共振的本义是"大运支与流年**引动的那一支**产生共振",性质型不是两支关系,
        # 合并会让 score 随可见性修复而漂移(反过拟合纪律:2019/2022 必须逐字节不变)。
        involved = set()
        involved_view = set()
        for i, z in enumerate(zhis):
            pn = PILLAR_NAMES[i]
            if {lz, z} in LIUCHONG:
                ev.append((f"流年支{lz}冲{pn}支{z}", 2.0, "冲", ("冲", z))); involved.add(i)
                if KE[GAN_WX[lg]] == GAN_WX[gans[i]] or KE[GAN_WX[gans[i]]] == GAN_WX[lg]:
                    ev.append((f"并天克地冲{pn}柱{pillars[i]}", 1.5, "天克地冲", ("天克地冲", pillars[i])))
            if {lz, z} in LIUHE:
                ev.append((f"流年支{lz}合{pn}支{z}", 1.2, "合", ("合", z))); involved.add(i)
            if {lz, z} in LIUHAI:
                ev.append((f"流年支{lz}穿{pn}支{z}", 1.8, "穿", ("穿", z))); involved.add(i)
            if lz == z:
                ev.append((f"流年支{lz}伏吟{pn}支", 1.5, "伏吟", ("伏吟", z))); involved.add(i)
            if gz == pillars[i]:
                ev.append((f"流年{gz}与{pn}柱全伏吟", 1.0, "伏吟", ("全伏吟", gz)))
        # 禄/刃被引动（v0.10 新维度：日主之根、立身之本被动）
        for i, z in enumerate(zhis):
            pn = PILLAR_NAMES[i]
            if lu_zhi and z == lu_zhi:
                if {lz, z} in LIUCHONG:
                    ev.append((f"流年支{lz}冲日主之禄（{pn}支{z}，根基位）", 2.0, "禄冲", ("禄冲", z)))
                elif {lz, z} in LIUHAI:
                    ev.append((f"流年支{lz}穿日主之禄（{pn}支{z}，根基位）", 1.8, "禄穿", ("禄穿", z)))
                elif {lz, z} in LIUHE:
                    ev.append((f"流年支{lz}合日主之禄（{pn}支{z}）", 1.2, "禄合", ("禄合", z)))
                elif lz == z:
                    ev.append((f"流年支{lz}伏吟日主之禄（{pn}支{z}）", 1.2, "禄伏", ("禄伏", z)))
            if ren_zhi and z == ren_zhi:
                if {lz, z} in LIUCHONG:
                    ev.append((f"流年支{lz}冲日主阳刃（{pn}支{z}）", 2.2, "刃冲", ("刃冲", z)))
                elif {lz, z} in LIUHAI:
                    ev.append((f"流年支{lz}穿日主阳刃（{pn}支{z}）", 1.8, "刃穿", ("刃穿", z)))
                elif {lz, z} in LIUHE:
                    ev.append((f"流年支{lz}合日主阳刃（{pn}支{z}）", 1.2, "刃合", ("刃合", z)))
        # v0.13 D2：日主得根（仅当原局四支本气层无日主五行时，流年本气根到位才计——虚根得实；
        # 不查喜忌，方向读法归推理层§7.2，从格护栏哲学不破）
        if day_root_missing and GAN_WX[CANG[lz][0][0]] == dw_scan:
            ev.append((f"流年支{lz}为日主{day_gan}之本气根到位（原局四支本气无{dw_scan}——虚根得实）",
                       1.8, "得根", None))
            involved_view.add(2)   # v0.14 E2:日主之根=立身之本 → 日柱(自身宫)
        # v0.13 D3：三合/三会分档进入——补全成局计分；含中神半合低权计分；虚拱（隔角无中神）仅标注
        gongti = []
        zx = lambda s: "".join(sorted(s, key=ZHI.index))
        for wx5, trio in SANHE.items():
            if lz in trio and not trio <= zhi_set and (trio - {lz}) <= zhi_set:
                ev.append((f"流年支{lz}补全{zx(trio)}三合{wx5}局"
                           f"（原局已有{zx(trio - {lz})}）", 2.0, "补三合", None))
                involved_view.update(i for i, z2 in enumerate(zhis) if z2 in trio - {lz})
        for wx5, trio in SANHUI.items():
            if lz in trio and not trio <= zhi_set and (trio - {lz}) <= zhi_set:
                ev.append((f"流年支{lz}补全{zx(trio)}三会{wx5}方"
                           f"（原局已有{zx(trio - {lz})}）", 2.0, "补三合", None))
                involved_view.update(i for i, z2 in enumerate(zhis) if z2 in trio - {lz})
        for i, z in enumerate(zhis):
            if z == lz:
                continue
            pn = PILLAR_NAMES[i]
            for wx5, trio in SANHE.items():
                if lz in trio and z in trio and not (trio - {lz, z}) <= zhi_set:
                    if lz == SANHE_MID[wx5] or z == SANHE_MID[wx5]:
                        ev.append((f"流年支{lz}半合{pn}支{z}（{wx5}局含中神）", 0.8, "合", ("半合", z)))
                        involved.add(i)
                    else:
                        gongti.append(f"流年支{lz}与{pn}支{z}同{zx(trio)}三合系"
                                      f"（虚拱{SANHE_MID[wx5]}，中神不现——各派认定不一，仅标注不计分）")
            for wx5, trio in SANHUI.items():
                if lz in trio and z in trio and not (trio - {lz, z}) <= zhi_set:
                    gongti.append(f"流年支{lz}与{pn}支{z}同{zx(trio)}三会系（拱会仅标注不计分）")
        if lz in kongwang_str:
            ev.append((f"流年支{lz}填实空亡", 2.0, "填实空亡", None))
            involved_view.update(i for i, z2 in enumerate(zhis) if z2 in kongwang_str)  # 坐空亡的柱;无则不绑
        for missing, nm, present in sanxing_partial:
            if lz == missing:
                ev.append((f"流年支{lz}补全三刑({present}+{lz}，{nm})", 2.5, "补三刑", None))
        for wx5, mz in MU_ZHI.items():
            if lz == mz and wx5 in wx_present:
                ev.append((f"流年支{lz}为{wx5}之墓（原局{wx5}星入墓引动）", 1.5, "入墓", ("入墓", mz)))
                involved_view.update(_wx_palaces(zhis, gans, wx5))   # 被墓之星所在宫
            if mz in zhis and {lz, mz} in LIUCHONG and wx5 in wx_present:
                ev.append((f"流年支{lz}冲开原局{wx5}墓{mz}", 1.8, "冲墓", ("冲墓", mz)))
                involved_view.update(_wx_palaces(zhis, gans, wx5))
        lg_ss = shishen(day_gan, lg)
        lg_grp = SHISHEN_GROUP[lg_ss]
        fill = None
        if lg_ss not in all_ss_present:
            fill = f"{lg_ss}（该星含藏干全缺）"; fw = 2.2
        elif lg_grp not in full_group:
            fill = f"{lg_grp}类（含藏干全缺）"; fw = 2.0
        elif lg_grp not in vis_group:
            fill = f"{lg_grp}类（干与支本气不显）"; fw = 1.0
            # v0.13 D1：虚则待实的"实"要看流年自身——流年干自坐本气同类根（干支一体）时，
            # 补入的星是实的，不该按虚透第三档压分（口传本义"虚透待支实"）
            if SHISHEN_GROUP[shishen(day_gan, CANG[lz][0][0])] == lg_grp:
                fill += "·流年干自坐本气根，干支一体虚透得实"; fw = 2.0
        if fill:
            ev.append((f"流年干{lg}补原局之{fill}——虚则待实", fw, "补缺", None))
            # 补缺**不绑宫位**(对 E2 方案的一处实测修正):"虚则待实"的语义是"原局缺这颗星、
            # 流年把它补上",宫位含义是全局而非某一宫。实测按"藏该十神组的支"绑,比劫类命中四个支
            # → 四宫全含,把每宫仅 3 席的分组挤成噪音。宁可它只靠得根/入墓定位。
            fill_marks.append({"year": yr, "干支": gz, "虚岁(近似)": yr - birth_year + 1,
                               "补": fill, "流年干十神": lg_ss})

        # v0.12 婚恋信号（口传四规则机械化；纯标注不计分，读法与优先级见象义层§7.3）
        hl = []
        if lz == ri_zhi:
            hl.append(f"配偶宫填实：坐下{ri_zhi}字重现（规则一）")
        if {lz, ri_zhi} in LIUHE:
            hl.append(f"配偶宫见六合：流年支{lz}合日支{ri_zhi}（规则一）")
        if {lz, ri_zhi} in ANHE:
            hl.append(f"配偶宫见暗合：流年支{lz}暗合日支{ri_zhi}（藏干本气五合）")
        if lz != ri_zhi and any(lz in t and ri_zhi in t for t in SANHE.values()):
            hl.append(f"配偶宫会局：流年支{lz}与日支{ri_zhi}同三合系（拱/半合——口传另有'合走'一读，方向按§7.2复核）")
        if gender == "男" and lg_ss in ("正财", "偏财"):
            hl.append(f"男命财星年：流年干{lg}={lg_ss}（规则二{'，正星力专' if lg_ss == '正财' else ''}）")
        elif gender == "女" and lg_ss in ("正官", "七杀"):
            hl.append(f"女命官星年：流年干{lg}={lg_ss}（规则二{'，正星力专' if lg_ss == '正官' else ''}）")
        if WUHE.get(lg) == day_gan and ({lz, ri_zhi} in LIUHE or {lz, ri_zhi} in ANHE):
            hl.append(f"鸳鸯合：流年干{lg}合日干{day_gan}＋流年支{lz}合配偶宫——干支双合日柱（口传强应期）")
        for z2 in natal_he_partners:
            if {lz, ri_zhi} in LIUCHONG or {lz, z2} in LIUCHONG:
                hl.append(f"冲开配偶宫原局之合：原局{ri_zhi}与{z2}相合，流年支{lz}冲之"
                          f"（规则四：原局带合要冲开，冲反为应期——方向仍按§7.2）")
                break
        if hl:
            sanxing_hit = any(k == "补三刑" for _d, _w, k, _k2 in ev) or \
                any(lz in combo for combo, _nm in sanxing_full_list)
            if sanxing_hit and lz != ri_zhi:
                hl.append("三刑挡道：该年婚恋信号带三刑纠缠——口传读'可谈但拉锯/不顺'，"
                          "干净应期看下一坐下引动年（填实之年按干净读，判据待校准）")
            hunlian_years.append({"year": yr, "干支": gz, "虚岁(近似)": yr - birth_year + 1, "信号": hl})

        # 同支重复递减（v0.10 治分数通胀）：同一关系类型对同值地支的第 n 次触发权重 ×0.5^(n-1)
        seen, s, trig, form_w = {}, 0.0, [], {}
        for desc, w, kind, key in ev:
            if key:
                n = seen.get(key, 0); seen[key] = n + 1
                if n:
                    w = round(w * (0.5 ** n), 2)
                    desc += f"（同支第{n+1}次，权重递减）"
            s += w; trig.append(desc)
            if kind in TRIGGER_FORM:
                form_w[kind] = form_w.get(kind, 0.0) + w
        dy = dayun_of(yr)
        if dy:
            if dy == gz:
                s += 2.5; form_w["岁运并临"] = form_w.get("岁运并临", 0.0) + 2.5
                trig.append(f"岁运并临({gz})")
            else:
                dz = dy[1]
                mult = 1.0
                if dz == lz and s > 0:
                    trig.append(f"大运{dy}与流年同支加力"); mult = 1.3
                else:
                    for i in sorted(involved):
                        zi = zhis[i]
                        same_triad = any(dz in t and zi in t for t in SANHE.values())
                        if {dz, zi} in LIUCHONG or {dz, zi} in LIUHE or dz == zi or same_triad:
                            trig.append(f"大运支{dz}同时引动{PILLAR_NAMES[i]}支（共振）")
                            mult = 1.4
                            break
                if mult != 1.0:
                    s *= mult
                    form_w = {k: v * mult for k, v in form_w.items()}
        if s >= 2.0 and trig:
            marks.append({
                "year": yr, "干支": gz, "虚岁(近似)": yr - birth_year + 1,
                "实际覆盖": f"{yr}年立春(约2月4日)—{yr+1}年立春前",
                "score": round(s, 2),
                "形态": [{"形态": TRIGGER_FORM[k][0], "可验证度": TRIGGER_FORM[k][1],
                        "句式": TRIGGER_FORM[k][2], "权重": round(v, 2)}
                       for k, v in sorted(form_w.items(), key=lambda x: -x[1])[:3]],
                "主形态": TRIGGER_FORM[max(form_w, key=form_w.get)][0] if form_w else "无",
                "形态族": ("性质型" if form_w and max(form_w, key=form_w.get) in NATURE_KINDS else "关系型"),
                "可验证度": (TRIGGER_FORM[max(form_w, key=form_w.get)][1] if form_w else "低"),
                "可指认分": round(sum(v for k, v in form_w.items()
                                  if TRIGGER_FORM.get(k, ("", "低"))[1] == "高"), 2),
                "流年干十神": shishen(day_gan, lg),
                "triggers": trig,
                "涉及宫位": sorted({f"{PILLAR_NAMES[i]}({GONG_LIUQIN[PILLAR_NAMES[i]]})" for i in involved | involved_view}),
                "涉及支本气十神": sorted({shishen(day_gan, CANG[zhis[i]][0][0]) for i in involved | involved_view}),
                **({"婚恋信号": hl} if hl else {}),
                **({"拱会提示": gongti} if gongti else {}),
                **(lambda yx: {"月析": yx} if yx else {})(yuexi_of(lg, lz, zhis, zhi_set, involved, day_gan)),
            })
    # v0.19 相邻年同触发提示（机械事实：如空亡同旬两支相邻→填实必连响两年，Case#7 重复文案的根源）
    byyear = {m["year"]: m for m in marks}
    def _trig_sig(mm):
        out = set()
        for t in mm["triggers"]:
            t2 = t.split("（")[0]
            if t2.startswith("流年支") and len(t2) > 4:
                out.add(t2[4:])  # 去掉"流年支X"，留关系+目标（跨年可比）
        return {x for x in out if x and "大运" not in x}
    for m in marks:
        nxt = byyear.get(m["year"] + 1)
        if not nxt:
            continue
        shared = sorted(_trig_sig(m) & _trig_sig(nxt))
        if shared:
            m["相邻年提示"] = (f"与{nxt['year']}年共享触发（{'、'.join(shared[:3])}）——相邻年同因，"
                            f"推理层两年合并出一条，锚取强年或'XXXX年前后'")
            nxt.setdefault("相邻年提示", f"与{m['year']}年共享触发——同因相邻年，合并出一条")
    marks.sort(key=lambda m: (-m["score"], m["year"]))
    # 同支系（12 年一轮）标注：同一流年支的其他年份，供推理层按年龄合理性选年
    by_zhi = {}
    for m in marks:
        by_zhi.setdefault(m["干支"][1], []).append(m["year"])
    for m in marks:
        others = [y for y in by_zhi[m["干支"][1]] if y != m["year"]]
        if others:
            m["同支系其他年"] = others
    brief = lambda m: {"year": m["year"], "干支": m["干支"], "虚岁(近似)": m["虚岁(近似)"],
                       "score": m["score"], "主形态": m["主形态"], "可指认分": m["可指认分"],
                       "句式提示": (m["形态"][0]["句式"] if m["形态"] else ""),
                       "triggers": m["triggers"][:3],
                       **({"同支系其他年": m["同支系其他年"]} if "同支系其他年" in m else {})}
    # 按宫位分组：以外显分排序（断事优先），同支系只留最强代表，避免一支垄断
    by_palace = {}
    for m in sorted(marks, key=lambda x: (-x["可指认分"], x["year"])):
        for p in m["涉及宫位"]:
            slot = by_palace.setdefault(p, [])
            if len(slot) < 3 and not any(s["干支"][1] == m["干支"][1] for s in slot):
                slot.append(brief(m))
    renzhi_rank = sorted([m for m in marks if m["可指认分"] > 0], key=lambda m: (-m["可指认分"], m["year"]))
    # v0.12 近三年速览（稳妥三关保底盘用：近三年好坏＋行运十神状态归因，见 SKILL Step3 降级链）
    recent3 = []
    for yr in range(max(birth_year + 1, as_of_year - 2), as_of_year + 1):
        gz3 = liu_nian_gz(yr)
        recent3.append({"年": yr, "干支": gz3, "虚岁(近似)": yr - birth_year + 1,
                        "流年干十神": shishen(day_gan, gz3[0]),
                        "流年支本气十神": shishen(day_gan, CANG[gz3[1]][0][0]),
                        "大运": dayun_of(yr)})
    return {"nature": "experimental_heuristic（触发权重无回测；这是应期候选标记，不是事件断言；"
                      "虚岁为近似值[未细分立春界]，事件内容由推理层按象义层§7 生成）",
            "range": f"{birth_year + 1}–{as_of_year}（仅过去与当年，未来不扫）",
            "选取提示": "断具体事件**必须同时看三处**：①『可指认榜』(按烈度排序) ②『性质型年』"
                    "(事件类型自明的年——得根/填实/补缺/补局;它们的 score 被累加制系统性压低,"
                    "低分是机制产物不是'这年没事') ③『按宫位分组』。**三处的年份并列考虑后再选**,"
                    "别只取任一处的榜首。总榜 score ＝盘面扰动烈度，与生活事件显著度不是一回事；"
                    "**读每条的『主形态』与『句式提示』决定怎么说**——冲＝那年做了一次，"
                    "伏吟＝同类事那年反复多次（不是'内心戏'，实测三亥伏吟年＝频繁换工作），"
                    "穿＝被慢慢磨，填实＝悬了很久的事落地，得根＝立身之本落地（新环境/新位置站稳），"
                    "补三合＝几条线拢到一起成局；『拱会提示』为虚拱标注（各派认定不一），只作辅色不作证据；"
                    "『同支系其他年』给出 12 年一轮的同型年份，按年龄可验证性选年（成年优先）；"
                    "**『性质型年』必须与可指认榜榜首并列看**——那些年的 score 被累加制系统性压低，但事件类型最明确（得根＝立身之本落地／填实＝悬很久的事落地／补缺＝这条线第一次到位）",
            "跨年提示": "干支年以立春(约2月4日)为界，非公历 1 月 1 日：某干支年的事件若发生在次年 1 月至立春前，"
                    "命主会记成次年；报出年份与命主记忆差一年时，先按立春界核对季节再判 miss",
            "marks": marks[:15],
            "可指认榜": [brief(m) for m in _diverse(renzhi_rank, 8, 3, 2)],
            "性质型年": [brief(m) for m in marks if m.get("形态族") == "性质型"],
            "性质型年_note": "流年支**自身属性**触发的年(得根/填实/补缺/补局/入墓)。它们的 score 天然低于"
                          "关系型年(结构上只产 1-3 条 vs 6-7 条),**低分是机制产物,不是'这年没事'**;"
                          "而它们的事件类型自明,正是'可指认'的本义——断具体事件时必须与可指认榜榜首并列"
                          "进入候选,选谁再按语义贴合度与命主可核实性定(选关系型年也可以,但要是在看过这些年之后)",
            "按宫位分组": by_palace,
            "婚恋应期表": hunlian_years,
            "婚恋应期_note": "口传四规则（2026-07）纯标注不计分：坐下填实/见合（含暗合）、男财女官年、鸳鸯合、"
                          "冲开原局合；带'三刑挡道'的年份读'可谈但拉锯'，冲开与三刑同现时三刑优先（对感情不利，非应期）；"
                          "读法与优先级见象义层§7.3；口传经验：前两条规则覆盖八九成恋爱时间（经验值，非回测）；"
                          "仅过去年份（红线不动，未来应期不出）"
                          + ("" if gender else "；【未提供性别，财星/官星年信号未标】"),
            "近三年速览": recent3,
            "标记总数": len(marks),
            "虚则待实": fill_marks,
            "虚则待实_note": "原局全缺/不显之星被流年干补上的年份全集（不受截断）；"
                          "全缺之星所主的线（如无正财盘之婚缘线）应期优先看此表——象义层§1.1"}


DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
TIME_RE = re.compile(r"^(\d{1,2}):(\d{1,2})$")


def parse_and_validate(a):
    m = DATE_RE.match(a.date.strip())
    if not m:
        fail("INVALID_DATE_FORMAT", f"--date 需为 YYYY-MM-DD，收到: {a.date}")
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1900 <= y <= 2100):
        fail("DATE_OUT_OF_RANGE", "仅支持 1900–2100 年")
    if a.leap and a.calendar != "lunar":
        fail("LEAP_REQUIRES_LUNAR", "--leap 只能与 --calendar lunar 同用")
    hh = mm = None
    if a.time:
        t = TIME_RE.match(a.time.strip())
        if not t:
            fail("INVALID_TIME_FORMAT", f"--time 需为 HH:MM，收到: {a.time}")
        hh, mm = int(t.group(1)), int(t.group(2))
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            fail("INVALID_TIME", f"时间越界: {a.time}（小时 0–23，分钟 0–59）")
    if a.calendar == "solar":
        try:
            datetime.date(y, mo, d)
        except ValueError:
            fail("INVALID_SOLAR_DATE", f"公历日期不存在: {a.date}")
    else:
        try:
            lm = -mo if a.leap else mo
            lunar = Lunar.fromYmdHms(y, lm, d, 12, 0, 0)
            sol = lunar.getSolar()
            back = sol.getLunar()
            if not (back.getYear() == y and abs(back.getMonth()) == mo and back.getDay() == d
                    and (back.getMonth() < 0) == bool(a.leap)):
                fail("INVALID_LUNAR_DATE", f"农历日期不存在或闰月标记不符: {a.date} leap={a.leap}")
            y, mo, d = sol.getYear(), sol.getMonth(), sol.getDay()
        except SystemExit:
            raise
        except Exception as e:
            fail("INVALID_LUNAR_DATE", f"农历日期无效: {a.date} leap={a.leap} ({e})")
    as_of = datetime.date.today()
    if a.as_of:
        am = DATE_RE.match(a.as_of.strip())
        if not am:
            fail("INVALID_AS_OF", f"--as-of 需为 YYYY-MM-DD，收到: {a.as_of}")
        try:
            as_of = datetime.date(int(am.group(1)), int(am.group(2)), int(am.group(3)))
        except ValueError:
            fail("INVALID_AS_OF", f"--as-of 日期不存在: {a.as_of}")
    return y, mo, d, hh, mm, as_of


def collect_warnings(y, mo, tz_arg):
    w = []
    if tz_arg is None and 1986 <= y <= 1991 and 4 <= mo <= 9:
        w.append("出生于中国夏令时试行期（1986–1991 夏季）：若出生记录为夏令时钟表时间，"
                 "请减 1 小时输入，或改用 --tz Asia/Shanghai 自动换算历史夏令时")
    if tz_arg is not None and "/" not in str(tz_arg):
        w.append("--tz 使用数字偏移时不含夏令时信息：若出生地当时实行夏令时，请自行核对；"
                 "建议改用 IANA 时区名（如 America/New_York）自动处理")
    return w


def meta_block(as_of):
    return {
        "ok": True, "schema_version": SCHEMA,
        "engine": f"guosanguan/paipan.py v{VERSION}（判定逻辑层：只出结构事实与实验性启发式，不出断语）",
        "as_of": as_of.isoformat(),
        "历法": "lunar_python（立春分界年柱、节气分界月柱；时柱由日干五鼠遁重算保证 sect 口径一致）",
        "时间口径": "北京时间统一制：全球出生按出生地时区换算至 UTC+8 标准时排盘（--tz 支持 IANA 名与数字偏移，"
                  "IANA 名自动处理历史夏令时，含中国 1986–1991）；不使用真太阳时/均时差（source_school 决策，与真太阳时派并存）",
        "口径声明": [
            "旺衰与显著性均为 experimental_heuristic，无校准数据，禁止当作概率或命中率",
            "结构信号除标 fact 外均为 candidate：仅邻接结构事实，强弱/喜忌/通关未判",
            "阳刃=五阳干刃（甲丙戊庚壬）；阴干刃、宫位-身体映射等派别分歧项不在本层输出",
            "天干五合、地支三会、做功/喜忌/应期判定尚未实现——缺失不等于命局无此象，推理层不得反向推断",
        ]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="YYYY-MM-DD（公历或农历，配合 --calendar）")
    ap.add_argument("--time", default=None, help="HH:MM")
    ap.add_argument("--gender", default=None, choices=["男", "女"], help="排大运必需；缺省则不排大运")
    ap.add_argument("--calendar", default="solar", choices=["solar", "lunar"])
    ap.add_argument("--leap", action="store_true", help="农历闰月（仅 --calendar lunar）")
    ap.add_argument("--tz", default=None,
                    help="出生地时区：IANA 名（America/New_York、Asia/Shanghai）或数字偏移（-5、5.5、+09:00）；"
                         "缺省=输入已是北京时间。IANA 名自动处理历史夏令时")
    ap.add_argument("--sect", type=int, default=2, choices=[1, 2], help="晚子时日柱流派：2=算当天(默认) 1=算次日")
    ap.add_argument("--scan-hours", action="store_true", help="时辰未知：扫描候选时辰（含早/晚子时、经度校正）")
    ap.add_argument("--as-of", default=None, help="当前大运/流年的计算基准日 YYYY-MM-DD（默认今天）")
    a = ap.parse_args()

    y, mo, d, hh, mm, as_of = parse_and_validate(a)
    tz = parse_tz(a.tz)
    warnings = collect_warnings(y, mo, a.tz)

    try:
        if a.scan_hours:
            # H-01：候选=当地钟表 12 时辰代表点＋晚子时两口径，逐一换算北京时间（可跨日）
            cands = [("子(早)", 0, 30, a.sect)] + [(ZHI[i], i * 2, 30, a.sect) for i in range(1, 12)] \
                + [("子(晚)·sect2", 23, 30, 2), ("子(晚)·sect1", 23, 30, 1)]
            rows = []
            for label, h0, m0, sect in cands:
                t1, crossed, _ = to_beijing(y, mo, d, h0, m0, tz)
                ch = build_chart(t1.year, t1.month, t1.day, t1.hour, t1.minute, sect)
                rows.append({
                    "候选": label + "时", "当地钟点": f"{h0:02d}:{m0:02d}",
                    "北京时间": t1.strftime("%Y-%m-%d %H:%M") + ("（跨日）" if crossed else ""),
                    "四柱": " ".join(ch["pillars"]),
                    "时柱十神": f"干{ch['detail'][3]['干十神']}/支{ch['detail'][3]['支本气十神']}",
                    "旺衰启发式": f"{ch['L1_wangshuai']['verdict']}({ch['L1_wangshuai']['score']})",
                    "月柱兄弟宫": f"{ch['pillars'][1]} 干{ch['detail'][1]['干十神']}/支{ch['detail'][1]['支本气十神']}",
                    "关键信号": [s["name"] for s in ch["signals"]][:6],
                })
            uniq = len({r["四柱"] for r in rows})
            print(json.dumps({**meta_block(as_of), "mode": "scan-hours",
                              "input": {"date": a.date, "calendar": a.calendar, "leap": a.leap,
                                        "gender": a.gender, "tz": a.tz, "sect_default": a.sect},
                              "warnings": warnings,
                              "note": f"共 {len(rows)} 个候选盘（当地钟表时辰，含晚子时两口径，已按北京时间统一制换算），"
                                      f"唯一四柱 {uniq} 个；请推理层挑跨行差异最大的可验证定性特征做判别提问（定盘）",
                              "rows": rows}, ensure_ascii=False, indent=1))
            return

        if hh is None:
            fail("MISSING_TIME", "缺少 --time；时辰未知请改用 --scan-hours 进入定盘流程")

        t1, crossed, tz_desc = to_beijing(y, mo, d, hh, mm, tz)
        ch = build_chart(t1.year, t1.month, t1.day, t1.hour, t1.minute, a.sect)
        ec = ch.pop("ec")
        # 时辰交界在奇数整点（1/3/…/23 时）；距最近交界的分钟数，供 SKILL 稳健性检查
        mins_since = ((t1.hour - 1) % 2) * 60 + t1.minute
        boundary = min(mins_since, 120 - mins_since)
        out = {**meta_block(as_of),
               "input": {"date": a.date, "time": a.time, "calendar": a.calendar, "leap": a.leap,
                         "gender": a.gender, "tz": a.tz, "sect": a.sect},
               "time_resolution": {"输入时间": f"{y:04d}-{mo:02d}-{d:02d} {hh:02d}:{mm:02d}",
                                    "换算": tz_desc,
                                    "北京时间": t1.strftime("%Y-%m-%d %H:%M"), "跨日": crossed,
                                    "距时辰交界分钟": boundary,
                                    "边界提示": ("<20 分钟：SKILL 要求加跑相邻时辰对照" if boundary < 20 else None)},
               "warnings": warnings, **ch}
        if a.gender in ("男", "女"):
            out["dayun"] = dayun_block(ec, 1 if a.gender == "男" else 0, t1.year, as_of,
                                       out["pillars"][2][0])
        out["L1_yingqi_scan"] = yingqi_scan(out["pillars"], out["pillars"][2][0], out["kongwang"],
                                            out.get("dayun", {}).get("大运", []), t1.year, as_of.year,
                                            a.gender)
        print(json.dumps(out, ensure_ascii=False, indent=1))
    except SystemExit:
        raise
    except Exception as e:
        fail("INTERNAL_ERROR", f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
