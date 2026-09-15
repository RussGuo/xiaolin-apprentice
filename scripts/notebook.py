#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小霖学徒 · 理法笔记:把小霖亲口确认过的断法追加进 references/lifa-notebook.md。
用法:
  python3 notebook.py add --json entry.json   # 追加一条,自动分配 L 编号,打印新编号
  python3 notebook.py list                    # 列出 编号 + 一句话断法 + 标签
  python3 notebook.py check                   # 校验格式(编号连续、字段齐全),commit 前跑

entry.json 字段(全为必填,除「边界」「记录日期」):
  断法       一句话断法,写在标题里;修订条目写「修订 L002」
  盘面条件   必须能在 card.md 上定位到的字 / 关系 / 喜忌
  断法内容   在上述条件下倾向什么
  边界       小霖确认时说的适用 / 不适用条件;缺省写「小霖未加边界」
  来源案例   C 开头三位数,如 C003
  小霖原话   反馈里对应的那句,原样
  记录日期   缺省取今天
  标签       字符串数组,如 ["感情", "涉及喜忌规则"]
"""
import argparse, datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NOTEBOOK = os.path.join(ROOT, "references", "lifa-notebook.md")

FIELDS = ["盘面条件", "断法", "边界", "来源案例", "小霖原话", "记录日期", "标签"]
REQUIRED = ["断法", "盘面条件", "断法内容", "来源案例", "小霖原话", "标签"]
HEAD_RE = re.compile(r"^### (L\d{3}) · (.+?)\s*$")
BULLET_RE = re.compile(r"^- ([^:：]+)[::](.*)$")


def die(msg):
    sys.exit("理法笔记:" + msg)


def read_notebook(path=NOTEBOOK):
    if not os.path.exists(path):
        die("找不到 " + path + ",先初始化笔记本(只写说明头,零条目)。")
    return open(path, encoding="utf-8").read()


def parse(text):
    """把笔记本解析成条目列表:[{"编号":..,"断法":..,"字段":{..},"行号":..}]"""
    entries, cur = [], None
    for i, line in enumerate(text.splitlines(), 1):
        m = HEAD_RE.match(line)
        if m:
            cur = {"编号": m.group(1), "断法": m.group(2), "字段": {}, "行号": i}
            entries.append(cur)
            continue
        if cur is None:
            continue
        b = BULLET_RE.match(line)
        if b:
            cur["字段"][b.group(1).strip()] = b.group(2).strip()
    return entries


def next_id(entries):
    n = 0
    for e in entries:
        n = max(n, int(e["编号"][1:]))
    return "L%03d" % (n + 1)


def cmd_add(args):
    try:
        data = json.load(open(args.json, encoding="utf-8"))
    except Exception as e:
        die("读不了 %s:%s" % (args.json, e))
    if not isinstance(data, dict):
        die("entry.json 顶层要是一个对象。")
    missing = [k for k in REQUIRED if not str(data.get(k) or "").strip() and not (k == "标签" and data.get(k))]
    if missing:
        die("缺必填字段:" + "、".join(missing))
    if not str(data.get("盘面条件") or "").strip():
        die("盘面条件不能为空 —— 条件要能在 card.md 上定位到。")
    case = str(data["来源案例"]).strip()
    if not re.fullmatch(r"C\d{3}", case):
        die("来源案例要写成 C 开头三位数(如 C003),现在是:" + case)
    tags = data["标签"]
    if isinstance(tags, str):
        tags = [tags]
    tags = [str(t).strip() for t in tags if str(t).strip()]
    if not tags:
        die("标签不能为空(写维度,如 感情 / 健康;涉及强弱喜忌判定另加「涉及喜忌规则」)。")

    text = read_notebook()
    entries = parse(text)
    new_id = next_id(entries)
    block = "\n".join([
        "### %s · %s" % (new_id, str(data["断法"]).strip()),
        "- 盘面条件:" + str(data["盘面条件"]).strip(),
        "- 断法:" + str(data["断法内容"]).strip(),
        "- 边界:" + (str(data.get("边界") or "").strip() or "小霖未加边界"),
        "- 来源案例:" + case,
        "- 小霖原话:" + str(data["小霖原话"]).strip(),
        "- 记录日期:" + (str(data.get("记录日期") or "").strip() or datetime.date.today().isoformat()),
        "- 标签:" + " / ".join(tags),
    ])
    with open(NOTEBOOK, "w", encoding="utf-8") as f:
        f.write(text.rstrip("\n") + "\n\n" + block + "\n")
    print(new_id)


def cmd_list(args):
    entries = parse(read_notebook())
    if not entries:
        print("(笔记本为空:还没有小霖确认过的理法条目)")
        return
    for e in entries:
        print("%s · %s    [%s]" % (e["编号"], e["断法"], e["字段"].get("标签", "")))


def cmd_check(args):
    path = args.path or NOTEBOOK
    entries = parse(read_notebook(path))
    errs = []
    for i, e in enumerate(entries, 1):
        want = "L%03d" % i
        if e["编号"] != want:
            errs.append("第 %d 条编号是 %s,应为 %s(编号要连续)" % (i, e["编号"], want))
        for k in FIELDS:
            v = e["字段"].get(k)
            if v is None:
                errs.append("%s 缺字段「%s」" % (e["编号"], k))
            elif not v.strip() and k != "边界":
                errs.append("%s 的「%s」是空的" % (e["编号"], k))
        c = e["字段"].get("来源案例", "")
        if c and not re.fullmatch(r"C\d{3}", c.strip()):
            errs.append("%s 的来源案例「%s」不是 C 开头三位数" % (e["编号"], c))
        if not e["断法"].strip():
            errs.append("%s 标题里没有一句话断法" % e["编号"])
    if errs:
        sys.exit("理法笔记格式有问题:\n  " + "\n  ".join(errs))
    print("理法笔记 OK:%d 条,编号连续,字段齐全。" % len(entries))


def main():
    ap = argparse.ArgumentParser(description="理法笔记:追加 / 列出 / 校验")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="追加一条确认过的理法")
    a.add_argument("--json", required=True)
    a.set_defaults(func=cmd_add)
    l = sub.add_parser("list", help="列出全部条目")
    l.set_defaults(func=cmd_list)
    c = sub.add_parser("check", help="校验笔记本格式")
    c.add_argument("--path")
    c.set_defaults(func=cmd_check)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
