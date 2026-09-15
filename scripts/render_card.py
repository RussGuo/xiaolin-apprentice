# -*- coding: utf-8 -*-
"""排盘卡片渲染:paipan.py JSON(+ 可选 xiji.py JSON)→ 自包含 HTML → Chrome 无头截图 PNG。
用法:python3 render_card.py sample.json [xiji.json] out_basename
"""
import json, sys, os, subprocess, datetime

GAN = "甲乙丙丁戊己庚辛壬癸"; ZHI = "子丑寅卯辰巳午未申酉戌亥"
GAN_WX = dict(zip(GAN, "木木火火土土金金水水")); GAN_YY = dict(zip(GAN, "阳阴阳阴阳阴阳阴阳阴"))
ZHI_WX = dict(zip(ZHI, "水土木木土火火土金金土水")); ZHI_YY = dict(zip(ZHI, "阳阴阳阴阳阴阳阴阳阴阳阴"))
ZHI_MAIN = dict(zip(ZHI, "癸己甲乙戊丙丁己庚辛戊壬"))
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
def shishen(dm, g):
    if g == dm: return "比肩"
    same = GAN_YY[dm] == GAN_YY[g]; a, b = GAN_WX[dm], GAN_WX[g]
    if a == b: return "劫财"
    if SHENG[a] == b: return "食神" if same else "伤官"
    if KE[a] == b: return "偏财" if same else "正财"
    if KE[b] == a: return "七杀" if same else "正官"
    if SHENG[b] == a: return "偏印" if same else "正印"
    return "?"
NAYIN = {}
_ny = ["海中金","炉中火","大林木","路旁土","剑锋金","山头火","涧下水","城头土","白蜡金","杨柳木","泉中水","屋上土","霹雳火","松柏木","长流水","沙中金","山下火","平地木","壁上土","金箔金","覆灯火","天河水","大驿土","钗钏金","桑柘木","大溪水","沙中土","天上火","石榴木","大海水"]
for i in range(60):
    NAYIN[GAN[i % 10] + ZHI[i % 12]] = _ny[i // 2]
# 十二长生:阳干顺行、阴干逆行,起长生位
_CS = ["长生","沐浴","冠带","临官","帝旺","衰","病","死","墓","绝","胎","养"]
_START = {"甲": "亥", "丙": "寅", "戊": "寅", "庚": "巳", "壬": "申", "乙": "午", "丁": "酉", "己": "酉", "辛": "子", "癸": "卯"}
def changsheng(dm, z):
    s = ZHI.index(_START[dm]); i = ZHI.index(z)
    k = (i - s) % 12 if GAN_YY[dm] == "阳" else (s - i) % 12
    return _CS[k]
def ganzhi_year(y):
    return GAN[(y - 4) % 10] + ZHI[(y - 4) % 12]
WX_COLOR = {"木": "#3E8E6E", "火": "#B24A2E", "土": "#A5722F", "金": "#8E7A2E", "水": "#2A6FBF"}

def main():
    src = sys.argv[1]; xiji_path = sys.argv[2] if len(sys.argv) > 3 else None
    out = sys.argv[-1]
    d = json.load(open(src, encoding="utf-8"))
    if not (xiji_path and os.path.exists(xiji_path)):
        sys.exit("强弱喜忌尚未推出(缺 xiji JSON),不渲染卡片")
    xj = json.load(open(xiji_path, encoding="utf-8"))
    dm = d["day_master"][0]; gender = d["input"]["gender"]
    zao = "乾造" if gender == "男" else "坤造"
    tr = d["time_resolution"]; as_of = d.get("as_of", "")
    birth_year = int(d["input"]["date"][:4])
    hour_zhi = d["pillars"][3][1]
    # ---- 四柱表
    rows = {"十神": [], "天干": [], "地支": [], "藏干": [], "纳音": [], "长生": [], "神煞": [], "宫位": []}
    sh_by_pos = {}
    for s in d["shensha"]:
        sh_by_pos.setdefault(s["at"][:2], []).append(s["name"])
    for det in d["detail"]:
        g, z = det["干"], det["支"]; pos = det["柱"]
        rows["十神"].append(det["干十神"] if det["干十神"] != "日主" else "日主")
        rows["天干"].append(f'<span class="big" style="color:{WX_COLOR[GAN_WX[g]]}">{g}</span><span class="wx">{GAN_YY[g]}{GAN_WX[g]}</span>')
        rows["地支"].append(f'<span class="big" style="color:{WX_COLOR[ZHI_WX[z]]}">{z}</span><span class="wx">{ZHI_YY[z]}{ZHI_WX[z]}</span>')
        lab = ["本气", "中气", "余气"]
        rows["藏干"].append("<br>".join(f'<span style="color:{WX_COLOR[GAN_WX[c["gan"]]]}">{c["gan"]}</span> {c["shishen"]}<span class="dim"> {lab[i] if i < 3 else ""}</span>' for i, c in enumerate(det["藏干"])))
        rows["纳音"].append(NAYIN[g + z])
        rows["长生"].append(changsheng(dm, z))
        rows["神煞"].append("<br>".join(sh_by_pos.get(pos + "支", []) + sh_by_pos.get(pos + "干", [])) or '<span class="dim">—</span>')
        rows["宫位"].append(det["宫位六亲"])
    def tr_row(name, cells, cls=""):
        return f'<tr class="{cls}"><th>{name}</th>' + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
    pillar_table = '<table class="pillars"><tr><th></th><th>年柱</th><th>月柱</th><th>日柱</th><th>时柱</th></tr>' + \
        tr_row("十神", rows["十神"], "ss") + tr_row("天干", rows["天干"], "gan") + tr_row("地支", rows["地支"], "zhi") + \
        tr_row("藏干", rows["藏干"], "cang") + tr_row("纳音", rows["纳音"]) + tr_row("长生", rows["长生"]) + \
        tr_row("神煞", rows["神煞"]) + tr_row("宫位", rows["宫位"]) + "</table>"
    # ---- 关系
    rel = []
    for r in d["interactions"]:
        pair = r["pair"].replace("年支", "年").replace("月支", "月").replace("日支", "日").replace("时支", "时")
        note = f'<span class="dim">({r["note"]})</span>' if r.get("note") else ""
        adj = '<span class="dim">相邻</span>' if r.get("相邻") else ""
        rel.append(f'<li><b>{r["type"]}</b> {pair} {adj} {note}</li>')
    # ---- 强弱喜忌
    if True:
        def fmt(items):
            return "、".join(f'{x["element"]}<span class="dim">{"·".join(x.get("tags", []))}</span>' if x.get("tags") else x["element"] for x in items) or "—"
        xi = sorted(xj.get("xi", []), key=lambda x: (x.get("rank") is None, x.get("rank") or 0))
        ji = sorted(xj.get("ji", []), key=lambda x: (x.get("rank") is None, x.get("rank") or 0))
        co = xj.get("char_overrides") or {}
        co_row = f'<tr><th>本字</th><td>{"、".join(f"{k} {v}" for k, v in co.items())}</td></tr>' if co else ""
        flags = f'<p class="note">标记:{";".join(xj["flags"])}</p>' if xj.get("flags") else ""
        xiji_html = f'''<div class="verdict"><span class="vlabel">{xj["verdict"]}</span></div>
        <table class="kv"><tr><th>喜</th><td>{fmt(xi)}</td></tr><tr><th>忌</th><td>{fmt(ji)}</td></tr><tr><th>中性</th><td>{fmt(xj.get("neutral", []))}</td></tr>{co_row}</table>{flags}'''
    # ---- 大运
    dy = d["dayun"]; cur = [x for x in dy["大运"] if x.get("当前大运(按as_of)")]
    dy_cells = []
    for x in dy["大运"]:
        g, z = x["干支"]; c = " cur" if x.get("当前大运(按as_of)") else ""
        dy_cells.append(f'<td class="{c.strip()}"><div class="dg" style="color:{WX_COLOR[GAN_WX[g]]}">{g}<span class="ssm">{x["干十神"]}</span></div><div class="dg" style="color:{WX_COLOR[ZHI_WX[z]]}">{z}<span class="ssm">{x["支本气十神"]}</span></div><div class="dim">{x["起于公历"]}–{x["止于"]}</div><div class="dim">{x["起于虚龄"]} 岁起</div></td>')
    dayun_table = '<table class="dayun"><tr>' + "".join(dy_cells) + "</tr></table>"
    # ---- 流年:当前大运十年 + 当前年高亮
    now_y = int(as_of[:4]) if as_of else datetime.date.today().year
    if cur:
        y0, y1 = cur[0]["起于公历"], cur[0]["止于"]
    else:
        y0, y1 = now_y - 3, now_y + 6
    ln_cells = []
    for y in range(y0, y1 + 1):
        gz = ganzhi_year(y); g, z = gz
        c = "cur" if y == now_y else ""
        ln_cells.append(f'<td class="{c}"><div class="dim">{y}</div><div class="dg" style="color:{WX_COLOR[GAN_WX[g]]}">{g}<span class="ssm">{shishen(dm, g)}</span></div><div class="dg" style="color:{WX_COLOR[ZHI_WX[z]]}">{z}<span class="ssm">{shishen(dm, ZHI_MAIN[z])}</span></div><div class="dim">{y - birth_year + 1} 岁</div></td>')
    liunian_table = '<table class="dayun liunian"><tr>' + "".join(ln_cells) + "</tr></table>"
    cur_label = f'{cur[0]["干支"]}大运({cur[0]["起于公历"]}–{cur[0]["止于"]})' if cur else "近年"
    # 大运顺逆:第一步大运相对月柱前进为顺,后退为逆
    mg, mz = d["pillars"][1]; fg, fz = dy["大运"][0]["干支"]
    direction = "顺行" if (GAN.index(fg) - GAN.index(mg)) % 10 == 1 else "逆行"
    boundary = tr.get("边界提示") or ""
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>排盘 · {zao}</title>
<style>
:root{{--paper:#FAF9F7;--ink:#26262C;--ink-2:#5C5C62;--ink-3:#9A9AA0;--line:rgba(38,38,44,.12);--wash:#F1EFEB;--accent:#B24A2E;
--display:"Noto Serif SC","Songti SC",serif;--body:"PingFang SC","Noto Sans SC","Helvetica Neue",sans-serif;--mono:"SF Mono",Menlo,monospace}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#E9E6E0;font-family:var(--body);color:var(--ink);font-size:14px;line-height:22px;padding:24px}}
.card{{width:1160px;margin:0 auto;background:var(--paper);padding:40px 48px 32px;border-radius:6px}}
.head{{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:1px solid var(--ink);padding-bottom:16px}}
.head h1{{font-family:var(--display);font-weight:400;font-size:30px;line-height:40px}}
.head .sub{{color:var(--ink-2);margin-top:4px}}
.head .right{{text-align:right;color:var(--ink-2);font-size:13px;line-height:20px}}
.kicker{{font-size:11px;letter-spacing:.14em;color:var(--ink-3);font-weight:500;margin:28px 0 10px}}
table{{border-collapse:collapse;width:100%}}
.pillars th{{font-weight:500;color:var(--ink-2);text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);width:11%}}
.pillars th:first-child{{width:8%;color:var(--ink-3);font-size:12px}}
.pillars td{{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}}
.pillars tr.gan td,.pillars tr.zhi td{{padding:6px 10px}}
.big{{font-family:var(--display);font-size:40px;line-height:44px;display:inline-block;width:48px}}
.wx{{color:var(--ink-3);font-size:12px;margin-left:6px}}
.dim{{color:var(--ink-3);font-size:12px}}
.ss td{{color:var(--ink-2)}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:32px}}
ul.rel{{list-style:none;columns:2;column-gap:24px}}
ul.rel li{{margin-bottom:4px}}
.verdict{{display:flex;align-items:baseline;gap:12px;margin-bottom:8px}}
.vlabel{{font-family:var(--display);font-size:28px;color:var(--accent)}}
.kv th{{text-align:left;font-weight:500;color:var(--ink-2);width:52px;padding:4px 0;vertical-align:top}}
.kv td{{padding:4px 0}}
.note{{color:var(--ink-2);font-size:12px;line-height:20px;margin-top:6px}}
.dayun td{{text-align:center;padding:8px 4px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);width:11.1%}}
.dayun td.cur{{background:var(--wash);border-radius:6px}}
.dg{{font-family:var(--display);font-size:26px;line-height:32px;display:flex;justify-content:center;align-items:baseline;gap:6px}}
.ssm{{font-family:var(--body);font-size:11px;color:var(--ink-3)}}
.liunian td{{width:10%}}
.foot{{margin-top:28px;padding-top:12px;border-top:1px solid var(--line);color:var(--ink-3);font-size:11px;line-height:18px;display:flex;justify-content:space-between}}
</style></head><body><div class="card">
<div class="head"><div><h1>{zao} · {"".join(d["pillars"][0])} {d["pillars"][1]} {d["pillars"][2]} {d["pillars"][3]}</h1>
<div class="sub">公历 {tr["北京时间"]}(北京时间)· 农历{d["lunar"]} {hour_zhi}时 · {gender}</div></div>
<div class="right">日主 <b>{dm}{GAN_WX[dm]}</b>({GAN_YY[dm]})<br>空亡 {d["kongwang"]}{("<br>" + boundary) if boundary else ""}</div></div>
<div class="kicker">四柱</div>
{pillar_table}
<div class="two">
<div><div class="kicker">地支关系</div><ul class="rel">{"".join(rel) or "<li>—</li>"}</ul></div>
<div><div class="kicker">强弱与喜忌</div>{xiji_html}</div>
</div>
<div class="kicker">大运 · {direction} · 起运{dy["起运"].replace("出生后","")}({dy["起运公历年"]} 年起)</div>
{dayun_table}
<div class="kicker">流年 · {cur_label}</div>
{liunian_table}

</div></body></html>"""

    # ---- 文本版(与卡片同源,供推断阶段整段喂给模型)
    lines = [f"{zao} {' '.join(d['pillars'])} · 公历 {tr['北京时间']}(北京时间)· 农历{d['lunar']} {hour_zhi}时 · {gender} · 日主 {dm}{GAN_WX[dm]}({GAN_YY[dm]}) · 空亡 {d['kongwang']}"]
    if boundary: lines.append("时辰提示:" + boundary)
    lines.append("四柱:")
    for det in d["detail"]:
        g, z = det["干"], det["支"]
        cang = " ".join(f"{c['gan']}{c['shishen']}" for c in det["藏干"])
        sh = "、".join(sh_by_pos.get(det["柱"] + "支", []) + sh_by_pos.get(det["柱"] + "干", [])) or "无"
        lines.append(f"  {det['柱']}柱 {g}{z}:天干{g}({GAN_YY[g]}{GAN_WX[g]},{det['干十神']}) 地支{z}({ZHI_YY[z]}{ZHI_WX[z]}) 藏干[{cang}] 纳音{NAYIN[g+z]} 长生{changsheng(dm, z)} 神煞[{sh}] 宫位{det['宫位六亲']}")
    lines.append("地支关系:" + ";".join(f"{r['type']} {r['pair']}{'(相邻)' if r.get('相邻') else ''}{'(' + r['note'] + ')' if r.get('note') else ''}" for r in d["interactions"]))
    def fmt_t(items):
        return "、".join(f"{x['element']}({'·'.join(x.get('tags', []))})" if x.get("tags") else x["element"] for x in items) or "无"
    lines.append(f"强弱喜忌:{xj['verdict']};喜 {fmt_t(xi)};忌 {fmt_t(ji)};中性 {fmt_t(xj.get('neutral', []))}" + (";本字 " + "、".join(f"{k}{v}" for k, v in (xj.get("char_overrides") or {}).items()) if xj.get("char_overrides") else "") + (";标记 " + ";".join(xj["flags"]) if xj.get("flags") else ""))
    lines.append(f"大运({direction},起运{dy['起运'].replace('出生后','')},{dy['起运公历年']} 年起,岁数为虚龄):" + ";".join(f"{x['干支']}({x['干十神']}/{x['支本气十神']}) {x['起于公历']}–{x['止于']} {x['起于虚龄']}岁起{'【当前】' if x.get('当前大运(按as_of)') else ''}" for x in dy["大运"]))
    lines.append(f"流年({cur_label}):" + ";".join(f"{y} {ganzhi_year(y)}({shishen(dm, ganzhi_year(y)[0])}/{shishen(dm, ZHI_MAIN[ganzhi_year(y)[1]])}) {y - birth_year + 1}岁{'【今年】' if y == now_y else ''}" for y in range(y0, y1 + 1)))
    open(out + ".md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
    open(out + ".html", "w", encoding="utf-8").write(html)
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.environ.get("CODEX_SANDBOX") or os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED"):
        # 在 Codex 沙箱(seatbelt)里启动 Chrome 会在 LaunchServices 注册时 abort 并生成崩溃报告,直接跳过截图
        print(out + ".html", out + ".md", "沙箱内不启动 Chrome:PNG 未生成。请在沙箱外(escalated)重跑 run.py 生成 card.png,或直接打开 card.html")
        return
    if not os.path.exists(chrome):
        print(out + ".html", out + ".md", "未找到 Chrome,只生成了 HTML")
        return
    subprocess.run([chrome, "--headless=new", "--hide-scrollbars", "--window-size=1256,1500", f"--screenshot={out}.png", "file://" + os.path.abspath(out + ".html")], capture_output=True)
    try:
        from PIL import Image
        im = Image.open(out + ".png").convert("RGB"); w, h = im.size
        px = im.load(); bg = px[2, 2]
        bottom = h
        for y in range(h - 1, 0, -1):
            if any(px[x, y] != bg for x in range(0, w, 8)): bottom = y; break
        im.crop((0, 0, w, min(h, bottom + 24))).save(out + ".png")
    except Exception as e:
        pass
    print(out + ".html", out + ".png", out + ".md")

if __name__ == "__main__":
    main()
