#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
喜忌判定 v1.0 —— `docs/debates/喜忌判定规则-伪代码-v0.1.md`(内容为 v1.0 生产定版,
2026-09-10,含 0911 工程勘误)的忠实实现。

原则(见伪代码抬头):短路判定 · 任何盘必出结果不拒答 · 四值标签 ·
大运流年不参与原局判定 · 地支只取本气不拆藏干 · 不看刑冲合会。

只实现伪代码写明的规则;「待定 / flag」一律只落 flag,不附加行为。
纯标准库,无第三方依赖。

用法:
    python3 xiji.py 庚午 壬午 甲子 戊辰
    python3 xiji.py --json paipan_output.json        # 取其 pillars 字段
"""

import json
import sys

RULE_VERSION = "v1.0"

# ============================================================================
# §0 输出结构 / 十神分类常量
# ============================================================================
BIJIE, YIN, SHISHANG, CAI, GUANSHA = "比劫", "印", "食伤", "财", "官杀"
HELP = {BIJIE, YIN}
DRAIN = {SHISHANG, CAI, GUANSHA}

VERDICTS = {"身强", "身弱", "从强", "从弱"}                       # §0 对外只允许四值(BUG-5)
DEGREES = {"强", "偏强", "偏弱", "弱", "弱而有库", "从格", "偏强·均衡两可"}
RULE_CLASSES = {"A0", "A1", "A2", "A3", "A3.5", "A3.6", "A4"}

# ============================================================================
# §1 常量与基础工具
# ============================================================================
WUXING_GAN = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
              "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
WUXING_ZHI = {"寅": "木", "卯": "木", "巳": "火", "午": "火", "申": "金", "酉": "金",
              "亥": "水", "子": "水", "辰": "土", "戌": "土", "丑": "土", "未": "土"}
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
WET_EARTH, DRY_EARTH = {"辰", "丑"}, {"未", "戌"}
SUMMER, WINTER = {"巳", "午", "未"}, {"亥", "子", "丑"}
WUXING = ["木", "火", "土", "金", "水"]


def element(x):
    """干或支 → 五行(地支只取本气,不拆藏干)。"""
    return WUXING_GAN.get(x) or WUXING_ZHI[x]


def ten_god(dm_el, el):
    if el == dm_el:
        return BIJIE
    if SHENG[el] == dm_el:
        return YIN
    if SHENG[dm_el] == el:
        return SHISHANG
    if KE[dm_el] == el:
        return CAI
    return GUANSHA


def god_el(dm_el, god):
    """反查十神对应五行。§0 勘误 5:反查唯一性为显式不变式,实现必须断言看守。"""
    hits = [el for el in WUXING if ten_god(dm_el, el) == god]
    assert len(hits) == 1, "god_el 反查不唯一: dm=%s god=%s hits=%s" % (dm_el, god, hits)
    return hits[0]


class Pillar(object):
    __slots__ = ("gan", "zhi")

    def __init__(self, gz):
        self.gan, self.zhi = gz[0], gz[1]


class Chart(object):
    def __init__(self, pillars):
        self.year, self.month, self.day, self.hour = [Pillar(p) for p in pillars]

    def values(self):
        return [self.year, self.month, self.day, self.hour]


def six(chart):      # 除日干、月支外六字
    return [chart.year.gan, chart.year.zhi, chart.month.gan,
            chart.day.zhi, chart.hour.gan, chart.hour.zhi]


def seven(chart):    # 除日元外七字
    return six(chart) + [chart.month.zhi]


def all_in(chars, dm_el, cls_set):
    return all(ten_god(dm_el, element(c)) in cls_set for c in chars)


def visible_gods(chart, dm_el):     # 透干(年/月/时三干)十神集合
    return {ten_god(dm_el, element(g)) for g in
            [chart.year.gan, chart.month.gan, chart.hour.gan]}


def present_gods(chart, dm_el):     # 七字十神集合
    return {ten_god(dm_el, element(c)) for c in seven(chart)}


def cai_visible_and_rooted(chart, dm_el):    # 财"天透地藏"
    cai = god_el(dm_el, CAI)
    gans = [chart.year.gan, chart.month.gan, chart.hour.gan]
    zhis = [p.zhi for p in chart.values()]
    return (any(element(g) == cai for g in gans)
            and any(element(z) == cai for z in zhis))


def cai_absent(chart, dm_el):                # 七字中无财五行
    cai = god_el(dm_el, CAI)
    return not any(element(c) == cai for c in seven(chart))


def water_with_root(chart):                  # 金未月:"有根气的水"(参数可调)
    zhis = [p.zhi for p in chart.values()]
    gans = [p.gan for p in chart.values()]
    if any(z in {"亥", "子"} for z in zhis):
        return True, None
    if any(g in {"壬", "癸"} for g in gans) and any(z in {"申", "辰", "丑"} for z in zhis):
        return True, "金未月·根气判定(藏干近似判据命中)"   # 近似判据,命中必留痕
    return False, None


def shishang_extremely_weak(chart, dm_el):   # 官杀月食伤"仅一粒天干且地支无根"
    ss = god_el(dm_el, SHISHANG)
    chars = [c for c in seven(chart) if element(c) == ss]
    return (len(chars) == 1 and chars[0] in WUXING_GAN
            and not any(element(p.zhi) == ss for p in chart.values()))


# ============================================================================
# §0 勘误:条目与 Result 容器
#   3. xi/ji 统一 {element, rank, tags[]};neutral 统一 {element, tags[]}
#   1. rank 是名次唯一真相源,tag 只写理由,不写"第一用神"字样(BUG-1)
#   4. tag() 为追加语义;R(verdict, degree, rule_class, flags) 构造,其余初始为空
# ============================================================================
def _clean_tag(t):
    """勘误 1:剥掉伪代码里写在 tag 里的"第一用神"字样,名次只由 rank 承载。"""
    if t == "第一用神":
        return None
    if t.startswith("第一用神·"):
        return t[len("第一用神·"):]
    return t


def E_(el, rank=None, *tags):
    ts = [x for x in (_clean_tag(t) for t in tags) if x]
    return {"element": el, "rank": rank, "tags": ts}


def N_(el, *tags):
    ts = [x for x in (_clean_tag(t) for t in tags) if x]
    return {"element": el, "tags": ts}


def tag(lst, el, text):
    """勘误 4:tag() 为追加语义。"""
    text = _clean_tag(text)
    for e in lst:
        if e["element"] == el and text and text not in e["tags"]:
            e["tags"].append(text)
    return lst


def elements(lst):
    return [e["element"] for e in lst]


def _renumber(lst):
    """勘误 2:rank 重排后必须连续 1..n;原本无名次者保持 None。"""
    n = 0
    for e in lst:
        if e["rank"] is not None:
            n += 1
            e["rank"] = n
    return lst


def promote_or_insert_rank1(lst, el, tag_text=None):
    """§6:need 已在 xi → 移至 rank1;不在 → 插入 rank1;其余顺延(重排后连续)。"""
    hit = next((e for e in lst if e["element"] == el), None)
    if hit is not None:
        lst.remove(hit)
    else:
        hit = E_(el)
    lst.insert(0, hit)
    hit["rank"] = 1
    # 其余按新顺序顺延(勘误 2:重排后连续 1..n);原本无名次者保持 None
    # (挂起项 2:A0/A2/A3 判强类不补排序,只有被提名的调候神拿到 rank1)
    _renumber(lst)
    if tag_text:
        tag(lst, el, tag_text)
    return lst


class Result(object):
    def __init__(self, verdict, degree, rule_class, flags=None):
        self.verdict = verdict
        self.degree = degree
        self.rule_class = rule_class
        self.flags = list(flags or [])
        self.xi = []
        self.ji = []
        self.neutral = []
        self.char_overrides = {}
        self.congge_bypass = False

    def to_dict(self):
        return {
            "verdict": self.verdict,
            "degree": self.degree,
            "rule_class": self.rule_class,
            "xi": self.xi,
            "ji": self.ji,
            "neutral": self.neutral,
            "char_overrides": dict(self.char_overrides),
            "flags": list(self.flags),
            "rule_version": RULE_VERSION,
        }


R = Result


# ============================================================================
# §2 公共裁定器(月干 + 日支;时干与其余字不参与)
# ============================================================================
def two_char(chart, dm_el):
    mg = ten_god(dm_el, element(chart.month.gan))
    dz = ten_god(dm_el, element(chart.day.zhi))
    if mg in HELP and dz in HELP:
        return "STRONG", []
    if mg in DRAIN and dz in DRAIN:
        return "WEAK", []
    return "WEAK", ["两字一帮一克"]          # §10 已定:平局归弱


# ============================================================================
# §3 强弱判定(短路;顺序敏感:A0→A1→A2→A3→A3.6→A3.5→A4)
# ============================================================================
def judge_strength(chart):
    dm_el = element(chart.day.gan)
    yue = chart.month.zhi
    yue_god = ten_god(dm_el, element(yue))
    S, SV = six(chart), seven(chart)
    flags = []

    # A0 真从格(粗暴版,真假从不辨)
    if all_in(SV, dm_el, DRAIN):
        return R("从弱", "从格", "A0", ["真从弱"])
    if all_in(SV, dm_el, HELP):
        return R("从强", "从格", "A0", ["真从强"])

    # A1 本气得令 → 无条件身强(含金生戌丑)
    BENQI = {"木": {"寅", "卯"}, "火": {"巳", "午"},
             "金": {"申", "酉", "戌", "丑"}, "水": {"亥", "子"}}
    if dm_el != "土" and yue in BENQI[dm_el]:
        return R("身强", "偏强" if all_in(S, dm_el, DRAIN) else "强", "A1", flags)

    # A2 土生四库月 → 默认身强(盗泄不破例;唯一例外辰月土虚)
    if dm_el == "土" and yue in {"辰", "戌", "丑", "未"}:
        if yue == "辰" and all_in(S, dm_el, DRAIN):
            return R("身弱", "偏弱", "A2", flags + ["土生辰月全盘克泄耗"])
        return R("身强", "强", "A2", flags)

    # A3 季尾墓库月
    if (dm_el, yue) == ("火", "未"):                    # 09-10 定版:直接判强
        return R("身强", "偏强·均衡两可", "A3",
                 flags + ["火未月·均衡两可(文案留缓冲)"])
    if (dm_el, yue) in {("木", "辰"), ("水", "丑")}:
        if all_in(S, dm_el, HELP):
            return R("身强", "偏强", "A3", flags)
        if all_in(S, dm_el, DRAIN):
            return R("身弱", "偏弱", "A3", flags)
        r, f = two_char(chart, dm_el)
        flags += f
        if (dm_el, yue) == ("水", "丑"):
            flags.append("丑月官杀当令·偏弱倾向")
        return R("身强" if r == "STRONG" else "身弱",
                 "偏强" if r == "STRONG" else "偏弱", "A3", flags)

    # A3.6 金生辰、未月(必须先于 A3.5 截获)
    if dm_el == "金" and yue == "辰":                   # 金之绝地;收紧版已转正
        if chart.day.zhi in {"申", "酉", "丑", "戌"}:    # 只认日支坐实根;比劫透干不算
            return R("身强", "偏强", "A3.6",
                     flags + ["金辰月坐根判强·收紧版(复核池观察)"])
        return R("身弱", "弱", "A3.6", flags)
    if dm_el == "金" and yue == "未":                   # 无水判弱,坐比肩不救
        ok, f = water_with_root(chart)
        if ok:
            return R("身强", "偏强", "A3.6", flags + ([f] if f else []))
        return R("身弱", "弱", "A3.6", flags + ["金未月无水"])

    # A3.5 印月 → 按身强思路
    if yue_god == YIN:
        if not any(ten_god(dm_el, element(p.zhi)) == BIJIE for p in chart.values()):
            flags.append("印月判强·日主无根")           # 只记触发事实,结论留给复核
        return R("身强", "强", "A3.5", flags)

    # A4 普通失令 → 身弱,无条件(死规则:无帮身阈值)
    if all_in(S, dm_el, HELP):
        flags.append("失令满盘印比·文案按均衡写")
    if (dm_el, yue) in {("木", "未"), ("火", "戌"), ("水", "辰")}:   # 自库月
        flags.append("自库月·弱而有库")
        if (dm_el, yue) == ("木", "未"):
            flags.append("格局:易有钱")
        if (dm_el, yue) == ("火", "戌"):
            flags.append("格局:固执")
        return R("身弱", "弱而有库", "A4", flags)
    return R("身弱", "弱", "A4", flags)


# ============================================================================
# §4 喜忌映射
# ============================================================================
def base_mapping(res, chart, dm_el):
    E = lambda g: god_el(dm_el, g)
    yue_god = ten_god(dm_el, element(chart.month.zhi))

    # A0 从格:顺势,喜忌与常规相反
    if res.rule_class == "A0":
        if res.verdict == "从弱":
            res.xi = [E_(E(SHISHANG)), E_(E(CAI)), E_(E(GUANSHA))]
            res.ji = [E_(E(YIN)), E_(E(BIJIE))]
        else:
            res.xi = [E_(E(YIN)), E_(E(BIJIE))]
            res.ji = [E_(E(SHISHANG)), E_(E(CAI)), E_(E(GUANSHA))]
        res.congge_bypass = True
        return res

    # 判弱:按月令十神细分
    if res.verdict == "身弱":
        if yue_god == GUANSHA:
            res.xi = [E_(E(YIN), 1, "第一用神·化杀通关"), E_(E(BIJIE), 2)]
            res.ji = [E_(E(GUANSHA), 1, "月令"), E_(E(CAI), 2)]
            if shishang_extremely_weak(chart, dm_el):
                res.ji += [E_(E(SHISHANG), 3, "以弱制强")]
                res.flags += ["官杀月食伤极弱"]
            else:
                res.neutral = [N_(E(SHISHANG), "制杀·中性")]
        elif yue_god == SHISHANG:
            res.xi = [E_(E(YIN), 1, "第一用神·制食伤"), E_(E(BIJIE), 2)]
            res.ji = [E_(E(SHISHANG), 1, "月令"), E_(E(CAI), 2), E_(E(GUANSHA), 3)]
        elif yue_god == CAI:
            res.xi = [E_(E(BIJIE), 1, "第一用神·克财"),
                      E_(E(YIN), 2, "印被财克·未必全好")]
            res.ji = [E_(E(CAI), 1, "月令"), E_(E(GUANSHA), 2, "财生官克身"),
                      E_(E(SHISHANG), 3)]
        elif yue_god == YIN:                    # 金辰/金未收紧产物(印月判弱)
            res.xi = [E_(E(BIJIE), 1, "第一用神·帮身"), E_(E(YIN), 2)]
            res.ji = [E_(E(GUANSHA), 1, "克身最重"), E_(E(CAI), 2), E_(E(SHISHANG), 3)]
        else:                                   # yue_god == BIJIE:土生辰月全盘克泄耗
            res.xi = [E_(E(YIN), 1, "生身"), E_(E(BIJIE), 2)]
            res.ji = [E_(E(GUANSHA), 1), E_(E(CAI), 2), E_(E(SHISHANG), 3)]
        return res

    # A1 比劫当令判强:第一用神存在性回退链
    if res.rule_class == "A1":
        if SHISHANG in visible_gods(chart, dm_el):
            res.xi = [E_(E(SHISHANG), 1, "第一用神·泄秀"), E_(E(GUANSHA), 2), E_(E(CAI), 3)]
        elif GUANSHA in present_gods(chart, dm_el):
            res.xi = [E_(E(GUANSHA), 1, "第一用神·制身"), E_(E(SHISHANG), 2), E_(E(CAI), 3)]
        else:
            res.xi = [E_(E(CAI), 1, "第一用神·回退")]
            res.flags += ["用至财星·层次存疑"]
        res.ji = [E_(E(BIJIE), 1), E_(E(YIN), 2)]
        return res

    # 印月判强(A3.5 / A3.6 判强):财破印
    if res.rule_class in {"A3.5", "A3.6"}:
        res.xi = [E_(E(CAI), 1, "第一用神·破印"), E_(E(SHISHANG), 2),
                  E_(E(GUANSHA), 3, "多数喜")]
        res.ji = [E_(E(YIN), 1)]
        res.neutral = [N_(E(BIJIE), "泄印·中性")]
        if cai_absent(chart, dm_el):
            res.flags += ["印月判强·无财·层次受限"]
        elif cai_visible_and_rooted(chart, dm_el):
            res.flags += ["印月判强·财天透地藏·好命"]
        return res

    # A2 / A3 判强:通用(内部排序待小霖,rank=None;挂起项 2:不造假第一用神)
    res.xi = [E_(E(SHISHANG)), E_(E(CAI)), E_(E(GUANSHA))]
    res.ji = [E_(E(YIN)), E_(E(BIJIE))]
    return res


# ============================================================================
# §5 [C] 月令忌神(死规则;从格豁免)
# ============================================================================
def monthly_taboo(res, chart):
    if res.congge_bypass:
        res.char_overrides[chart.month.zhi] = "喜(顺势)"
    else:
        # 只压制"字",不动五行级喜忌
        res.char_overrides[chart.month.zhi] = "忌"
    return res


# ============================================================================
# §6 [D] 调候(未丑月第一用神;从格顺势优先;维护五行唯一不变式)
# ============================================================================
def tiaohou(res, chart):
    yue = chart.month.zhi
    need = "水" if yue in SUMMER else "火" if yue in WINTER else None
    if need is None:
        return res                                   # 春秋不调候(辰戌不调)

    # 从格保护:调候神若属从格之忌 → 不豁免、不提升,顺势优先,仅留痕
    if res.congge_bypass and need in elements(res.ji):
        res.flags += ["从格·调候让位于顺势"]
        return res

    was_ji = need in elements(res.ji)
    was_neutral = need in elements(res.neutral)
    res.ji = _renumber([j for j in res.ji if j["element"] != need])       # 从忌豁免
    res.neutral = [n for n in res.neutral if n["element"] != need]        # 从中性豁免

    if yue in {"未", "丑"}:
        # "这类盘第一时间先调候" → 调候神升为第一用神,原第一顺延
        promote_or_insert_rank1(res.xi, need, tag_text="第一用神·调候")
        if was_ji:
            tag(res.xi, need, "本为忌·语义带压力/代价")
    else:                                            # 巳午 / 亥子月:只补标签
        if need in elements(res.xi):
            tag(res.xi, need, "调候·inherent")
        elif was_ji or was_neutral:
            res.xi.append(E_(need, None, "调候·overridden"))
        else:
            res.xi.append(E_(need, None, "调候·added"))
    return res


# ============================================================================
# §7 [E] 土湿燥修正(仅当土为该日主克泄耗、且 verdict==身强)
# ============================================================================
def earth_split(res, chart, dm_el):
    if ten_god(dm_el, "土") not in DRAIN:            # 金(土=印)、土日主(比劫)不适用
        return res
    if res.verdict != "身强":                        # 判弱/从格不拆
        return res
    yue = chart.month.zhi
    if yue in WET_EARTH:                             # 锚点:壬癸水生丑月判强(0819)
        for z in WET_EARTH:
            res.char_overrides[z] = "忌"
        for z in DRY_EARTH:
            res.char_overrides[z] = "参半"           # 参半偏喜,带官杀代价
    elif yue in DRY_EARTH:                           # 保守镜像,命中留痕
        for z in DRY_EARTH:
            res.char_overrides[z] = "忌" if z == yue else "参半"
        res.flags += ["E-燥土镜像·保守实现"]
        # 0911 全量实测:戌月不存在判强路径,本分支实际仅火未月可达。保留为防御性代码。
    return res


# ============================================================================
# §0 不变式断言 + §11 契约校验
# ============================================================================
def validate(pillars):
    """§11-1 / 0911 补充:域外字符必须拒绝报错,不猜不修。"""
    if not isinstance(pillars, (list, tuple)) or len(pillars) != 4:
        raise ValueError("四柱不全:需要 [年, 月, 日, 时] 四个干支")
    for i, gz in enumerate(pillars):
        if not isinstance(gz, str) or len(gz) != 2:
            raise ValueError("第 %d 柱非法:%r(应为两字干支)" % (i + 1, gz))
        if gz[0] not in WUXING_GAN:
            raise ValueError("第 %d 柱天干域外:%r" % (i + 1, gz[0]))
        if gz[1] not in WUXING_ZHI:
            raise ValueError("第 %d 柱地支域外:%r" % (i + 1, gz[1]))


def assert_invariants(res):
    assert res.verdict in VERDICTS, "verdict 非四值:%s" % res.verdict
    assert res.degree in DEGREES, "degree 非法:%s" % res.degree
    assert res.rule_class in RULE_CLASSES, "rule_class 非法:%s" % res.rule_class
    # 勘误 2:rank 连续 1..n;无名次者 None
    for lst, name in ((res.xi, "xi"), (res.ji, "ji")):
        ranks = [e["rank"] for e in lst if e["rank"] is not None]
        assert ranks == list(range(1, len(ranks) + 1)), "%s rank 不连续:%s" % (name, ranks)
        # 勘误 1:名次唯一真相源在 rank,tag 不写"第一用神"
        for e in lst:
            assert "第一用神" not in "".join(e["tags"]), "tag 混入名次:%s" % e
            assert set(e.keys()) == {"element", "rank", "tags"}, "条目字段不符 §0"
    for e in res.neutral:
        assert set(e.keys()) == {"element", "tags"}, "neutral 条目字段不符 §0"
    # §0 不变式:同一五行在 xi / ji / neutral 中至多出现一次
    els = elements(res.xi) + elements(res.ji) + elements(res.neutral)
    assert len(els) == len(set(els)), "五行重复出现:%s" % els
    assert all(e in WUXING for e in els), "五行域外:%s" % els
    return res


# ============================================================================
# §8 主流程
# ============================================================================
def xiji(chart):
    dm_el = element(chart.day.gan)
    res = judge_strength(chart)
    res = base_mapping(res, chart, dm_el)
    res = monthly_taboo(res, chart)
    res = tiaohou(res, chart)
    res = earth_split(res, chart, dm_el)
    return assert_invariants(res)


def judge(pillars):
    """公开入口:四柱干支 [年, 月, 日, 时] → §0 Result(dict)。"""
    validate(pillars)
    return xiji(Chart(list(pillars))).to_dict()


# ============================================================================
# CLI
# ============================================================================
def _pillars_from_json(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    p = data.get("pillars") if isinstance(data, dict) else None
    if not p:
        raise SystemExit("JSON 中未找到 pillars 字段:%s" % path)
    return p


def main(argv):
    args = argv[1:]
    if len(args) == 2 and args[0] == "--json":
        pillars = _pillars_from_json(args[1])
    elif len(args) == 4:
        pillars = args
    else:
        raise SystemExit("用法: python3 xiji.py 年柱 月柱 日柱 时柱 | --json <paipan.json>")
    print(json.dumps(judge(pillars), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv)
