#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小霖学徒 · 第三阶段归档:校验案例目录齐全 → 分配案例代号 → 更新 cases/index.md → 校验理法笔记 → commit + push。
用法:
  python3 archive.py cases/1990-06-01-0800-女 [--case-id C003]
不给 --case-id 就从 cases/index.md 取下一个。push 失败只警告,不影响归档已经落盘的结果。
"""
import argparse, datetime, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INDEX = os.path.join(ROOT, "cases", "index.md")
NOTEBOOK_REL = os.path.join("references", "lifa-notebook.md")
NEEDED = ["card.md", "02-初判.md", "03-小霖反馈.md", "04-定版.md", "05-理法候选.md"]
ROW_RE = re.compile(r"^\|\s*(C\d{3})\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*$")
HEADER = ["# 案例索引", "", "| 案例代号 | 日期 | 目录 | 状态 |", "|---|---|---|---|"]


def die(msg):
    sys.exit("归档:" + msg)


def git(*args, check=True):
    r = subprocess.run(["git", "-C", ROOT] + list(args), capture_output=True, text=True)
    if check and r.returncode != 0:
        die("git %s 失败:\n%s" % (" ".join(args), (r.stderr or r.stdout).strip()))
    return r


def read_index():
    if not os.path.exists(INDEX):
        return []
    rows = []
    for line in open(INDEX, encoding="utf-8").read().splitlines():
        m = ROW_RE.match(line)
        if m:
            rows.append(list(m.groups()))
    return rows


def write_index(rows):
    lines = list(HEADER) + ["| %s | %s | %s | %s |" % tuple(r) for r in rows]
    os.makedirs(os.path.dirname(INDEX), exist_ok=True)
    open(INDEX, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def next_case_id(rows):
    n = 0
    for r in rows:
        n = max(n, int(r[0][1:]))
    return "C%03d" % (n + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case_dir")
    ap.add_argument("--case-id")
    a = ap.parse_args()

    case_dir = os.path.abspath(a.case_dir)
    if not os.path.isdir(case_dir):
        die("案例目录不存在:" + case_dir)
    rel = os.path.relpath(case_dir, ROOT)
    if rel.startswith(".."):
        die("案例目录要在仓库的 cases/ 下,现在是:" + case_dir)

    missing = [n for n in NEEDED if not os.path.exists(os.path.join(case_dir, n))]
    if missing:
        die("案例目录缺文件:" + "、".join(missing))

    rows = read_index()
    dir_name = os.path.basename(case_dir)
    existing = next((r for r in rows if r[2] == rel or r[2] == dir_name), None)
    if a.case_id:
        if not re.fullmatch(r"C\d{3}", a.case_id):
            die("--case-id 要写成 C 开头三位数,如 C003。")
        clash = next((r for r in rows if r[0] == a.case_id and r[2] != rel), None)
        if clash:
            die("案例代号 %s 已经给了 %s。" % (a.case_id, clash[2]))
        case_id = a.case_id
    else:
        case_id = existing[0] if existing else next_case_id(rows)

    date = datetime.date.today().isoformat()  # 归档日期;出生日期只留在目录名里,不进笔记本
    row = [case_id, date, rel, "已定版"]
    if existing:
        rows[rows.index(existing)] = row
    else:
        rows.append(row)
    rows.sort(key=lambda r: r[0])
    write_index(rows)
    print("索引已更新:%s | %s | %s | 已定版" % (case_id, date, rel))

    r = subprocess.run([sys.executable, os.path.join(HERE, "notebook.py"), "check"], capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        die("理法笔记没过校验,先改笔记本再归档:\n" + (r.stderr or "").strip())

    git("add", rel, os.path.relpath(INDEX, ROOT), NOTEBOOK_REL)
    c = git("commit", "-m", "%s 定版归档" % case_id, check=False)
    if c.returncode != 0:
        out = (c.stdout + c.stderr).strip()
        if "nothing to commit" in out or "无文件要提交" in out:
            print("警告:没有新变更可提交(可能已经归档过)。")
        else:
            die("commit 失败:\n" + out)
    else:
        print("已提交:%s 定版归档" % case_id)

    p = git("push", "origin", "HEAD", check=False)
    if p.returncode != 0:
        print("警告:push 失败,归档已落盘,稍后手动 push。\n" + (p.stderr or p.stdout).strip()[-500:])
    else:
        print("已 push。")


if __name__ == "__main__":
    main()
