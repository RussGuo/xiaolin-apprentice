#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""notebook.py / archive.py 的回归。全部在临时目录里跑,不碰真笔记本、不碰真 cases/。
用法:python3 test_notebook.py
"""
import json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name + (("  << " + detail) if (detail and not cond) else ""))


def run(root, script, *args):
    return subprocess.run([sys.executable, os.path.join(root, "scripts", script)] + list(args),
                          capture_output=True, text=True, cwd=root)


def sandbox(tmp):
    """搭一个假仓库:scripts/ 拷贝真脚本,references/ 放空笔记本,cases/ 放空索引,git init。"""
    os.makedirs(os.path.join(tmp, "scripts"))
    for f in ("notebook.py", "archive.py"):
        shutil.copy(os.path.join(HERE, f), os.path.join(tmp, "scripts", f))
    os.makedirs(os.path.join(tmp, "references"))
    open(os.path.join(tmp, "references", "lifa-notebook.md"), "w", encoding="utf-8").write(
        "# 理法笔记\n\n- 只记小霖亲口确认过的理法。\n- 条目只增不删。\n- 要改用「修订」条目引用原编号。\n")
    os.makedirs(os.path.join(tmp, "cases"))
    open(os.path.join(tmp, "cases", "index.md"), "w", encoding="utf-8").write(
        "# 案例索引\n\n| 案例代号 | 日期 | 目录 | 状态 |\n|---|---|---|---|\n")
    for cmd in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", tmp] + cmd, capture_output=True, text=True)
    subprocess.run(["git", "-C", tmp, "add", "-A"], capture_output=True, text=True)
    subprocess.run(["git", "-C", tmp, "commit", "-qm", "init"], capture_output=True, text=True)
    return tmp


def entry(**kw):
    d = {"断法": "官杀混杂又透干,感情上早年多波动", "盘面条件": "日主庚金,月令午火,官杀透干",
         "断法内容": "倾向于二十五岁前感情反复,难定",
         "边界": "", "来源案例": "C001", "小霖原话": "这个盘官杀都露出来了,早年感情肯定定不下来",
         "标签": ["感情"]}
    d.update(kw)
    return d


def write_json(tmp, data, name="entry.json"):
    p = os.path.join(tmp, name)
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return p


def make_case(root, dir_name, skip=()):
    d = os.path.join(root, "cases", dir_name)
    os.makedirs(d, exist_ok=True)
    for f in ("card.md", "02-初判.md", "03-小霖反馈.md", "04-定版.md", "05-理法候选.md"):
        if f in skip:
            continue
        open(os.path.join(d, f), "w", encoding="utf-8").write("# %s(测试占位)\n" % f)
    return d


def test_notebook(tmp):
    print("notebook.py")
    nb = os.path.join(tmp, "references", "lifa-notebook.md")
    r = run(tmp, "notebook.py", "check")
    check("空笔记本能过 check", r.returncode == 0, r.stderr)

    r = run(tmp, "notebook.py", "add", "--json", write_json(tmp, entry()))
    check("add 第一条分配 L001", r.returncode == 0 and r.stdout.strip() == "L001", r.stdout + r.stderr)
    text = open(nb, encoding="utf-8").read()
    check("标题格式正确", "### L001 · 官杀混杂又透干,感情上早年多波动" in text, text)
    check("边界留空时写「小霖未加边界」", "- 边界:小霖未加边界" in text, text)
    check("字段齐全", all(("- %s:" % k) in text for k in
                       ("盘面条件", "断法", "来源案例", "小霖原话", "记录日期", "标签")), text)

    r = run(tmp, "notebook.py", "add", "--json",
            write_json(tmp, entry(断法="修订 L001", 边界="只在月令火旺时成立", 标签=["感情", "涉及喜忌规则"]), "e2.json"))
    check("add 第二条分配 L002", r.returncode == 0 and r.stdout.strip() == "L002", r.stdout + r.stderr)
    text = open(nb, encoding="utf-8").read()
    check("修订条目写得进去", "### L002 · 修订 L001" in text, text)
    check("边界与多标签落盘", "- 边界:只在月令火旺时成立" in text and "- 标签:感情 / 涉及喜忌规则" in text, text)

    r = run(tmp, "notebook.py", "list")
    check("list 打出编号和标签", "L001" in r.stdout and "L002" in r.stdout and "涉及喜忌规则" in r.stdout, r.stdout)
    r = run(tmp, "notebook.py", "check")
    check("两条后 check 通过", r.returncode == 0, r.stderr)

    before = open(nb, encoding="utf-8").read()
    for name, bad in (("缺必填字段报错", entry(小霖原话="")),
                      ("盘面条件为空报错", entry(盘面条件="   ")),
                      ("来源案例格式错报错", entry(来源案例="C3")),
                      ("标签为空报错", entry(标签=[]))):
        r = run(tmp, "notebook.py", "add", "--json", write_json(tmp, bad, "bad.json"))
        check(name, r.returncode != 0, r.stdout)
    check("报错时不写坏笔记本", open(nb, encoding="utf-8").read() == before)

    tampered = os.path.join(tmp, "tampered.md")
    open(tampered, "w", encoding="utf-8").write(before.replace("### L002", "### L005"))
    r = subprocess.run([sys.executable, os.path.join(tmp, "scripts", "notebook.py"), "check", "--path", tampered],
                       capture_output=True, text=True, cwd=tmp)
    check("编号不连续被 check 抓到", r.returncode != 0 and "连续" in (r.stderr + r.stdout), r.stderr)


def test_archive(tmp):
    print("archive.py")
    d1 = make_case(tmp, "1990-06-01-0800-女")
    r = run(tmp, "archive.py", d1)
    idx = open(os.path.join(tmp, "cases", "index.md"), encoding="utf-8").read()
    check("首个案例拿到 C001", r.returncode == 0 and "| C001 |" in idx, r.stdout + r.stderr + idx)
    check("目录写进索引", "cases/1990-06-01-0800-女" in idx, idx)
    check("状态写已定版", "| 已定版 |" in idx, idx)
    log = subprocess.run(["git", "-C", tmp, "log", "--oneline", "-1"], capture_output=True, text=True).stdout
    check("commit 信息是「C001 定版归档」", "C001 定版归档" in log, log)
    check("没有远端时 push 只警告不报错", r.returncode == 0 and "警告" in r.stdout, r.stdout)
    tracked = subprocess.run(["git", "-C", tmp, "-c", "core.quotepath=false", "ls-files", "cases/1990-06-01-0800-女"],
                             capture_output=True, text=True).stdout
    check("五个 md 都入库", all(f in tracked for f in ("card.md", "02-初判.md", "03-小霖反馈.md", "04-定版.md", "05-理法候选.md")), tracked)

    d2 = make_case(tmp, "1988-11-20-1400-男")
    r = run(tmp, "archive.py", d2, "--case-id", "C007")
    idx = open(os.path.join(tmp, "cases", "index.md"), encoding="utf-8").read()
    check("指定 case-id 生效", r.returncode == 0 and "| C007 |" in idx, r.stdout + r.stderr)
    d3 = make_case(tmp, "1990-06-02-0800-女")
    r = run(tmp, "archive.py", d3)
    idx = open(os.path.join(tmp, "cases", "index.md"), encoding="utf-8").read()
    check("下一个代号接着最大号往后排 C008", "| C008 |" in idx, idx)
    r = run(tmp, "archive.py", d3, "--case-id", "C001")
    check("代号撞车被拦下", r.returncode != 0, r.stdout)

    d4 = make_case(tmp, "1999-01-01-0900-女", skip=("04-定版.md", "05-理法候选.md"))
    r = run(tmp, "archive.py", d4)
    check("缺文件报错并点名", r.returncode != 0 and "04-定版.md" in r.stderr and "05-理法候选.md" in r.stderr, r.stderr)
    r = run(tmp, "archive.py", os.path.join(tmp, "cases", "不存在"))
    check("目录不存在报错", r.returncode != 0, r.stdout)

    nb = os.path.join(tmp, "references", "lifa-notebook.md")
    open(nb, "a", encoding="utf-8").write("\n### L009 · 坏条目\n- 盘面条件:x\n")
    d5 = make_case(tmp, "2000-02-02-1000-男")
    r = run(tmp, "archive.py", d5)
    check("笔记本坏了就不许归档", r.returncode != 0, r.stdout + r.stderr)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        sandbox(tmp)
        test_notebook(tmp)
        test_archive(tmp)
    print("\n通过 %d,失败 %d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项:" + "、".join(FAIL))
        sys.exit(1)


if __name__ == "__main__":
    main()
