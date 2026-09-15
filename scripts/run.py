#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小霖学徒 · 第一阶段:出生时间 + 性别 → 排盘 → 强弱喜忌 → 命盘卡片。
用法:python3 run.py --date 1990-06-01 --time 08:00 --gender 女 [--tz Asia/Tokyo] [--calendar lunar] [--leap] [--out DIR]
输出:cases/<日期-时间-性别>/{paipan.json, xiji.json, card.html, card.png, card.md(文本版,喂给推断阶段)}
"""
import argparse, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True); ap.add_argument("--time", required=True)
    ap.add_argument("--gender", required=True, choices=["男", "女"])
    ap.add_argument("--tz"); ap.add_argument("--calendar", default="solar"); ap.add_argument("--leap", action="store_true")
    ap.add_argument("--as-of"); ap.add_argument("--out")
    a = ap.parse_args()
    out = a.out or os.path.join(ROOT, "cases", f"{a.date}-{a.time.replace(':', '')}-{a.gender}")
    os.makedirs(out, exist_ok=True)
    cmd = [sys.executable, os.path.join(HERE, "paipan.py"), "--date", a.date, "--time", a.time, "--gender", a.gender, "--calendar", a.calendar]
    if a.tz: cmd += ["--tz", a.tz]
    if a.leap: cmd += ["--leap"]
    if a.as_of: cmd += ["--as-of", a.as_of]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        pp = json.loads(r.stdout)
    except Exception:
        sys.exit("排盘脚本无输出:\n" + r.stderr[-2000:])
    open(os.path.join(out, "paipan.json"), "w", encoding="utf-8").write(json.dumps(pp, ensure_ascii=False, indent=1))
    if not pp.get("ok"):
        sys.exit("排盘失败,请核对输入:" + json.dumps(pp, ensure_ascii=False))
    r2 = subprocess.run([sys.executable, os.path.join(HERE, "xiji.py"), "--json", os.path.join(out, "paipan.json")], capture_output=True, text=True)
    if r2.returncode != 0:
        sys.exit("喜忌脚本失败:\n" + r2.stderr[-2000:])
    open(os.path.join(out, "xiji.json"), "w", encoding="utf-8").write(r2.stdout)
    r3 = subprocess.run([sys.executable, os.path.join(HERE, "render_card.py"), os.path.join(out, "paipan.json"), os.path.join(out, "xiji.json"), os.path.join(out, "card")], capture_output=True, text=True)
    if r3.returncode != 0:
        sys.exit("卡片渲染失败:\n" + r3.stderr[-2000:])
    xj = json.loads(r2.stdout)
    tr = pp.get("time_resolution", {})
    print(json.dumps({
        "pillars": pp["pillars"], "day_master": pp["day_master"], "verdict": xj["verdict"],
        "xi": [x["element"] for x in sorted(xj["xi"], key=lambda x: (x.get("rank") is None, x.get("rank") or 0))],
        "ji": [x["element"] for x in sorted(xj["ji"], key=lambda x: (x.get("rank") is None, x.get("rank") or 0))],
        "neutral": [x["element"] for x in xj.get("neutral", [])],
        "边界提示": tr.get("边界提示"), "warnings": pp.get("warnings", []),
        "card_png": os.path.join(out, "card.png"), "card_html": os.path.join(out, "card.html"), "card_md": os.path.join(out, "card.md"),
    }, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
