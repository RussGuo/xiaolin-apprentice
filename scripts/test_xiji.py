#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
喜忌判定 v1.0 回归门禁 —— 伪代码 §9 的 13 条(10 小霖金标签盘 + 3 结构锚点)。
§11-5:上线前 §9 回归 13 条全过;回归表只增不删。

期望值一字不改地照抄 §9 表格;表格里写不全的地方(下标注 NOTE)保留解读说明,
不为了跑绿而改 xiji.py。
"""
from __future__ import print_function
import sys

from xiji import judge

# 每条:编号, 四柱, 期望 dict, §9 原文, 备注
#   verdict      : §9「期望(v1.0)」列的四值标签
#   rule_class   : 表中标注了才断言
#   degree       : 表中标注了才断言
#   xi_rank1     : 第一用神(表中写作「喜 X(1·…)」)
#   xi_contains  : 表中点名的喜用五行(全部必须在 xi 内)
#   ji           : 表中点名的忌神五行集合(集合相等,除非标了 ji_contains)
#   ji_contains  : 表中用「…」省略时,只断言包含
#   neutral      : 中性档五行集合
#   overrides    : char_overrides 的子集断言
#   flags_any    : flags 中必须出现的子串
CASES = [
    dict(
        id="R01", pillars=["辛丑", "辛丑", "甲戌", "庚午"],
        row="| 辛丑 辛丑 甲戌 庚午 | **从弱**;喜 火(1·调候)土金;忌 木水;月令丑=喜(顺势) |",
        verdict="从弱", rule_class="A0", degree="从格",
        xi_rank1="火", xi_contains=["火", "土", "金"], ji={"木", "水"},
        neutral=set(), overrides={"丑": "喜(顺势)"}, flags_any=["真从弱"],
        note="A0 从弱 + 丑月调候升第一用神(§10「调候不得凌驾于从格之忌」的 R01 原例:"
             "火不在从弱之忌内,照常升 rank1)",
    ),
    dict(
        id="R02", pillars=["庚午", "乙酉", "丙午", "甲午"],
        row="| 庚午 乙酉 丙午 甲午 | 身弱(A4);喜 火(1·克财)木;忌 金官… |",
        verdict="身弱", rule_class="A4",
        xi_rank1="火", xi_contains=["火", "木"], ji_contains=["金", "水"],
        overrides={"酉": "忌"},
        note="表中忌列写作「金官…」(省略号)→ 只断言包含 金(财·月令)与 水(官杀);"
             "午午午自刑改喜用属永不建模项,表中已注明不建模",
    ),
    dict(
        id="R03", pillars=["庚午", "戊寅", "戊申", "戊午"],
        row="| 庚午 戊寅 戊申 戊午 | 身弱;喜 火(1·化杀)土;中性 金 |",
        verdict="身弱", rule_class="A4",
        xi_rank1="火", xi_contains=["火", "土"], ji={"木", "水"},
        neutral={"金"}, overrides={"寅": "忌"},
    ),
    dict(
        id="R04", pillars=["癸巳", "壬戌", "丁未", "丙午"],
        row="| 癸巳 壬戌 丁未 丙午 | 身弱(弱而有库·固执);喜 木(1·制食伤)火 |",
        verdict="身弱", rule_class="A4", degree="弱而有库",
        xi_rank1="木", xi_contains=["木", "火"], ji={"土", "金", "水"},
        neutral=set(), overrides={"戌": "忌"},
        flags_any=["自库月·弱而有库", "格局:固执"],
    ),
    dict(
        id="R05", pillars=["戊寅", "乙丑", "庚午", "戊寅"],
        row="| 戊寅 乙丑 庚午 戊寅 | 身强(A1);喜 火(1·调候+制身)水木;忌 土金;丑本字忌 |",
        verdict="身强", rule_class="A1",
        xi_rank1="火", xi_contains=["火", "水", "木"], ji={"金", "土"},
        neutral=set(), overrides={"丑": "忌"},
    ),
    dict(
        id="R06", pillars=["甲午", "辛未", "丁未", "丙午"],
        row="| 甲午 辛未 丁未 丙午 | **身强(偏强·均衡两可)**;喜 水(1·调候)金;"
            "未本字忌、戌参半;忌 木火 |",
        verdict="身强", rule_class="A3", degree="偏强·均衡两可",
        xi_rank1="水", xi_contains=["水", "金"], ji={"木", "火"},
        neutral=set(), overrides={"未": "忌", "戌": "参半"},
        flags_any=["火未月·均衡两可(文案留缓冲)", "E-燥土镜像·保守实现"],
        note="表中喜列只点了 水金,未点 土;A3 通用映射里 土(食伤)在 xi 内,"
             "由 [E] 层在「字」级拆成 未忌/戌参半(§7 注:只压制字,不动五行级喜忌)。"
             "故本例不断言 xi 集合相等,只断言 水金在内。",
    ),
    dict(
        id="R07", pillars=["庚寅", "庚辰", "辛亥", "甲午"],
        row="| 庚寅 庚辰 辛亥 甲午 | **身弱(金辰月收紧:日支亥非根)**;喜 金(1·帮身)土;忌 火木水 |",
        verdict="身弱", rule_class="A3.6", degree="弱",
        xi_rank1="金", xi_contains=["金", "土"], ji={"火", "木", "水"},
        neutral=set(), overrides={"辰": "忌"},
    ),
    dict(
        id="R08", pillars=["戊寅", "己未", "庚午", "甲申"],
        row="| 戊寅 己未 庚午 甲申 | 身弱(金未月无水);喜 水(1·调候)土金;忌 木火 |",
        verdict="身弱", rule_class="A3.6",
        xi_rank1="水", xi_contains=["水", "土", "金"], ji={"木", "火"},
        neutral=set(), overrides={"未": "忌"}, flags_any=["金未月无水"],
    ),
    dict(
        id="R09", pillars=["辛卯", "丁酉", "壬午", "癸卯"],
        row="| 辛卯 丁酉 壬午 癸卯 | 身强(A3.5);喜 火(1·破印)木土;忌 金;中性 水;"
            "flag 财天透地藏 |",
        verdict="身强", rule_class="A3.5",
        xi_rank1="火", xi_contains=["火", "木", "土"], ji={"金"},
        neutral={"水"}, overrides={"酉": "忌"},
        flags_any=["印月判强·财天透地藏·好命"],
        note="金标签附注「语气按均衡偏强收敛」只约束文案;A3.5 的 degree 定版为「强」,"
             "不据此改码(§11-2:degree 不直接展示)",
    ),
    dict(
        id="R10", pillars=["丙子", "辛丑", "戊申", "癸丑"],
        row="| 丙子 辛丑 戊申 癸丑 | 身强(A2);喜 火(1·调候)金水木;忌 土(丑本字) |",
        verdict="身强", rule_class="A2",
        xi_rank1="火", xi_contains=["火", "金", "水", "木"], ji={"土"},
        neutral=set(), overrides={"丑": "忌"},
    ),
    dict(
        id="R11", pillars=["庚申", "辛丑", "壬申", "庚子"],
        row="| 一添盘(壬水丑月,贴身皆印比) | 身强(A3);喜 火(1·调候)木;"
            "湿土忌、燥土参半;忌 金水 |",
        verdict="身强", rule_class="A3", degree="偏强",
        xi_rank1="火", xi_contains=["火", "木"], ji={"金", "水"},
        neutral=set(),
        overrides={"丑": "忌", "辰": "忌", "未": "参半", "戌": "参半"},
        note="§9 只给了口径「壬水丑月,贴身皆印比」,未给八字 → 按该口径构造"
             "庚申 辛丑 壬申 庚子(月干辛=印、日支申=印,六字全印比,月支丑破从强)。"
             "喜列同 R06:土(官杀)在 xi 内,由 [E] 层在字级拆成湿土忌/燥土参半。",
    ),
    dict(
        id="R12", pillars=["己卯", "戊辰", "乙未", "丙戌"],
        row="| 己卯 戊辰 乙未 丙戌 | 身弱(A3 木辰两字皆克泄耗);喜 木(1·克财)水;忌 土金火 |",
        verdict="身弱", rule_class="A3", degree="偏弱",
        xi_rank1="木", xi_contains=["木", "水"], ji={"土", "金", "火"},
        neutral=set(), overrides={"辰": "忌"},
    ),
    dict(
        id="R13", pillars=["甲寅", "甲寅", "甲子", "乙亥"],
        row="| 构造:七字全印比 | **从强**;喜印比;月令喜(顺势) |",
        verdict="从强", rule_class="A0", degree="从格",
        xi_contains=["水", "木"], ji={"火", "土", "金"},
        neutral=set(), overrides={"寅": "喜(顺势)"}, flags_any=["真从强"],
        note="§9 只写「构造:七字全印比」→ 取 甲寅 甲寅 甲子 乙亥(甲木日元,七字皆比劫/印)。"
             "A0 不排序,故不断言 rank1。",
    ),
]


def check(case):
    res = judge(case["pillars"])
    errs = []

    def eq(name, got, want):
        if got != want:
            errs.append("%s: got %r, want %r" % (name, got, want))

    eq("verdict", res["verdict"], case["verdict"])
    if case.get("rule_class"):
        eq("rule_class", res["rule_class"], case["rule_class"])
    if case.get("degree"):
        eq("degree", res["degree"], case["degree"])

    xi_els = [e["element"] for e in res["xi"]]
    if case.get("xi_rank1"):
        r1 = [e["element"] for e in res["xi"] if e["rank"] == 1]
        eq("xi rank1", r1, [case["xi_rank1"]])
    for el in case.get("xi_contains", []):
        if el not in xi_els:
            errs.append("xi 缺 %s(实得 %s)" % (el, xi_els))

    ji_els = {e["element"] for e in res["ji"]}
    if "ji" in case:
        eq("ji", ji_els, case["ji"])
    for el in case.get("ji_contains", []):
        if el not in ji_els:
            errs.append("ji 缺 %s(实得 %s)" % (el, sorted(ji_els)))

    if "neutral" in case:
        eq("neutral", {e["element"] for e in res["neutral"]}, case["neutral"])

    for ch, v in case.get("overrides", {}).items():
        if res["char_overrides"].get(ch) != v:
            errs.append("char_overrides[%s]: got %r, want %r"
                        % (ch, res["char_overrides"].get(ch), v))

    for f in case.get("flags_any", []):
        if f not in res["flags"]:
            errs.append("flag 缺 %r(实得 %s)" % (f, res["flags"]))

    eq("rule_version", res["rule_version"], "v1.0")
    return res, errs


def main():
    rows, failed = [], 0
    for c in CASES:
        res, errs = check(c)
        ok = not errs
        failed += 0 if ok else 1
        rows.append((c["id"], " ".join(c["pillars"]), "PASS" if ok else "FAIL",
                     res["verdict"], res["rule_class"], res["degree"], errs))
    w = max(len(r[1]) for r in rows)
    print("| 用例 | 四柱 | 结果 | verdict | rule_class | degree |")
    print("|---|---|---|---|---|---|")
    for rid, p, st, v, rc, dg, _ in rows:
        print("| %s | %-*s | %s | %s | %s | %s |" % (rid, w, p, st, v, rc, dg))
    for rid, p, st, _, _, _, errs in rows:
        if errs:
            print("\n%s %s 失败明细:" % (rid, p))
            for e in errs:
                print("   - " + e)
    print("\n%d/%d passed" % (len(rows) - failed, len(rows)))
    notes = [c for c in CASES if c.get("note")]
    if notes:
        print("\n解读说明(表格未写死之处,代码未迁就):")
        for c in notes:
            print("  [%s] %s" % (c["id"], c["note"]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
