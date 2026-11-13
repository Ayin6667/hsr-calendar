#!/usr/bin/env python3
"""Honkai: Star Rail MONTH calendar (月历) — HTML.

Usage: python hsr_monthly_html.py YYYY MM [DD]

Reads hsr_events_YYYY_MM.json next to this script, writes calendar.html.

Renders:
  * a 7-column month grid; each cell lists events STARTING that day and shows a
    thin colour band for every event SPANNING that day
  * a full-month horizontal timeline with duration bars
  * a red "now" line positioned from the real clock (Beijing time), which keeps
    moving while the page stays open (see the injected script)
"""
import html
import io
import json
import os
import re
import sys
from datetime import date, datetime, time as dtime, timedelta, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
CST = timezone(timedelta(hours=8))
ROW_PITCH = 54

# 彩线排序优先级：版本 > 卡池 > 双倍 > 活动 > 备注（不能用字母序，否则 activity 会插到 version 前）
TYPE_ORDER = {"version": 0, "war": 1, "light": 2, "activity": 3, "note": 4}

TYPE_META = {
    "version": ("版本", "★", "var(--c-version)"),
    "war": ("跃迁", "◆", "var(--c-war)"),
    "light": ("光锥", "◇", "var(--c-light)"),
    "activity": ("活动", "●", "var(--c-activity)"),
    "note": ("公告", "■", "var(--c-note)"),
}
SOURCE_META = {
    "official": ("🟢", "官方确认", "ok"),
    "verified": ("🟡", "多方印证", "warn"),
    "doubtful": ("🔴", "存疑待核", "bad"),
}
DOW = ["一", "二", "三", "四", "五", "六", "日"]
THEME_JS = (
    "(function(){var K='hsr-theme',s=null;try{s=localStorage.getItem(K)}catch(e){}"
    "var m=window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches;"
    "document.documentElement.setAttribute('data-theme',s||(m?'light':'dark'));})();"
)
TOGGLE_JS = (
    "(function(){var K='hsr-theme',r=document.documentElement,btn=document.getElementById('themeBtn');"
    "function cur(){return r.getAttribute('data-theme')==='light'?'light':'dark';}"
    "if(btn){btn.addEventListener('click',function(){"
    "var n=cur()==='light'?'dark':'light';r.setAttribute('data-theme',n);"
    "try{localStorage.setItem(K,n)}catch(e){}});}"
    "if(window.matchMedia){var mq=window.matchMedia('(prefers-color-scheme: light)');"
    "var h=function(e){var s=null;try{s=localStorage.getItem(K)}catch(x){}"
    "if(!s){r.setAttribute('data-theme',e.matches?'light':'dark')}};"
    "if(mq.addEventListener){mq.addEventListener('change',h)}else if(mq.addListener){mq.addListener(h)}}"
    "})();"
)
CSS = """
:root{
  /* 墨 / 纸：深色偏冷墨，浅色偏暖纸 */
  --bg:#0d0e11; --fg:#eceef2; --dim:#9aa1ad; --faint:#6e7581;
  --line:rgba(255,255,255,.09); --line-2:rgba(255,255,255,.16);
  --surface:#131418; --surface-2:#191b21; --surface-3:#0a0b0e;
  --cell-bg:#131418; --cell-pad:#0a0b0e; --cell-past-op:.42;
  --grid-line:rgba(255,255,255,.055); --day-line:rgba(255,255,255,.03);
  --track-bg:#0a0b0e; --track-bd:rgba(255,255,255,.12);
  --chip-bg:transparent; --pill-bg:rgba(255,255,255,.055); --pill-bd:rgba(255,255,255,.16);
  --divider:rgba(255,255,255,.09); --shadow:rgba(0,0,0,.5);
  --accent:#f5c451; --red:#ff5d6c; --red-ink:#0d0e11; --red-glow:rgba(255,93,108,.22);
  --weekend:#e0a05a; --num:#eceef2; --today-num:#ff5d6c;
  --c-version:#ff6b81; --c-war:#ff9f43; --c-light:#e8c547; --c-activity:#4ade80; --c-note:#6b9bff;
  --ok:#4ade80; --warn:#e8c547; --bad:#ff8a8a;
  --bar-bg:#131418; --bar-ink:#eceef2;
  --code-bg:rgba(255,255,255,.06); --code-fg:#9db8f0;
  --soft:14%;
}
[data-theme="light"]{
  --bg:#faf9f7; --fg:#16181d; --dim:#5f6673; --faint:#8e94a1;
  --line:rgba(20,24,32,.11); --line-2:rgba(20,24,32,.2);
  --surface:#ffffff; --surface-2:#f4f3ef; --surface-3:#f3f2ee;
  --cell-bg:#ffffff; --cell-pad:#f3f2ee; --cell-past-op:.45;
  --grid-line:rgba(20,24,32,.06); --day-line:rgba(20,24,32,.035);
  --track-bg:#ffffff; --track-bd:rgba(20,24,32,.14);
  --chip-bg:transparent; --pill-bg:rgba(20,24,32,.045); --pill-bd:rgba(20,24,32,.16);
  --divider:rgba(20,24,32,.11); --shadow:rgba(20,30,60,.10);
  --accent:#a8752a; --red:#c8203a; --red-ink:#ffffff; --red-glow:rgba(200,32,58,.16);
  --weekend:#a35a12; --num:#16181d; --today-num:#c8203a;
  --c-version:#c8203a; --c-war:#b8620a; --c-light:#8a6d00; --c-activity:#0f7a45; --c-note:#2b4fa8;
  --ok:#0f7a45; --warn:#8a6d00; --bad:#bf2a2a;
  --bar-bg:#ffffff; --bar-ink:#16181d;
  --code-bg:rgba(20,24,32,.05); --code-fg:#2b4fa8;
  --soft:11%;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--fg);
font-family:"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",system-ui,sans-serif;
font-size:14px;line-height:1.5;padding:44px 40px 72px;min-width:1420px;
-webkit-font-smoothing:antialiased;transition:background .18s,color .18s}

/* ---------- 主题切换 ---------- */
.theme-toggle{position:fixed;top:20px;right:22px;z-index:9999;display:inline-flex;align-items:center;gap:7px;
background:transparent;color:var(--dim);border:1px solid var(--line);border-radius:999px;padding:7px 13px;
font-family:inherit;font-size:11.5px;font-weight:600;letter-spacing:.06em;line-height:1;cursor:pointer;
transition:color .16s,border-color .16s}
.theme-toggle:hover{color:var(--fg);border-color:var(--line-2)}
.theme-toggle svg{display:block;flex:0 0 auto}
.tt-moon{display:none}
[data-theme="light"] .tt-sun{display:none}
[data-theme="light"] .tt-moon{display:block}
.tt-lbl::after{content:"浅色"}
[data-theme="light"] .tt-lbl::after{content:"深色"}

/* ---------- 页框：杂志风不画卡片，只留最大宽度 ---------- */
.frame{position:relative;max-width:1560px;margin:0 auto}

/* ---------- 页头：左对齐大标题 + 细线 ---------- */
.head{display:flex;flex-direction:column;gap:7px;padding-bottom:14px;margin-bottom:22px;
border-bottom:1px solid var(--line)}
.title{font-size:26px;font-weight:800;letter-spacing:-.012em;line-height:1.22}
.title span{font-size:13px;font-weight:500;color:var(--faint);margin-left:11px;letter-spacing:.1em}
.meta{font-size:12.5px;color:var(--dim);letter-spacing:.015em}
.meta b{color:var(--fg);font-weight:700}
.sep{margin:0 9px;color:var(--line-2);font-weight:400}

/* ---------- 星期表头 ---------- */
.dow{display:grid;grid-template-columns:repeat(7,1fr);gap:1px;background:var(--line);
border:1px solid var(--line);border-bottom:0}
.dow div{background:var(--surface-2);text-align:center;padding:9px 0;
font-size:11px;font-weight:700;letter-spacing:.2em;color:var(--faint);transition:background .18s}
.dow div.we{color:var(--weekend)}

/* ---------- 月网格：1px 线连成表格 ---------- */
.grid{display:grid;grid-template-columns:repeat(7,1fr);gap:1px;background:var(--line);
border:1px solid var(--line)}
.cell{position:relative;min-height:200px;background:var(--cell-bg);padding:9px 10px 11px;
display:flex;flex-direction:column;gap:5px;transition:background .18s}
.cell.pad{background:var(--cell-pad)}
.cell.past{opacity:var(--cell-past-op)}
.cell.today{background:var(--surface-2)}
.cell.today::before{content:"";position:absolute;left:0;right:0;top:0;height:2px;background:var(--today-num)}
.dnum{font-size:16px;font-weight:600;color:var(--num);letter-spacing:-.01em;
font-variant-numeric:tabular-nums}
.cell.past .dnum{color:var(--faint)}
.cell.today .dnum{color:var(--today-num);font-weight:800}
.cell.we .dnum{color:var(--weekend)}
.dnum small{font-size:10.5px;color:var(--faint);font-weight:600;margin-left:5px;letter-spacing:0}

/* ---------- 当日开始条目：色点 + 文字，无底色 ---------- */
.chips{display:flex;flex-direction:column;gap:2px}
.chip{display:flex;align-items:center;gap:5px;font-size:11.5px;line-height:1.45;
padding:1px 3px;border-radius:2px;color:var(--tc);background:transparent;
transition:background .14s,color .14s}
.chip .ct{flex:1 1 auto;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chip:hover{background:color-mix(in srgb,var(--tc) 12%,transparent)}
.more{font-size:11px;color:var(--faint);padding-left:3px}

/* ---------- 格内跨天彩带：细色条 + 极淡底色 ---------- */
.spans{margin-top:auto;display:flex;flex-direction:column;gap:2px}
.spans i,.spans .sg{display:flex;align-items:center;gap:4px;height:16px;border-radius:2px;
border-left:2px solid var(--tc);background:color-mix(in srgb,var(--tc) var(--soft),transparent);
color:var(--fg);font-size:10.5px;font-weight:600;line-height:1;padding:0 6px;
overflow:hidden;white-space:nowrap;font-style:normal;transition:background .14s}
.spans i:hover,.spans .sg:hover{background:color-mix(in srgb,var(--tc) 26%,transparent)}
.spans .sn{flex:1 1 auto;overflow:hidden;text-overflow:ellipsis}
.spans .go{flex:0 0 auto;font-size:8.5px;opacity:.6}
.smore{font-family:inherit;font-size:10px;font-weight:600;color:var(--faint);
background:transparent;border:0;border-bottom:1px dotted var(--line-2);border-radius:0;
padding:0 0 1px;cursor:pointer;text-align:left;line-height:1.35;align-self:flex-start;letter-spacing:.02em}
.smore:hover{color:var(--accent);border-bottom-color:var(--accent)}
/* 特异性必须高于 .spans .sg(0,2,0)，故用三个类(0,3,0) */
.spans .sg.extra{display:none}
.cell.expanded .spans .sg.extra{display:flex}

/* ---------- 整月时间轴 ---------- */
.tlwrap{margin-top:32px}
.tlhead{display:flex;align-items:baseline;justify-content:space-between;
margin-bottom:12px;padding-bottom:9px;border-bottom:1px solid var(--line)}
.tlhead h3{font-size:14px;font-weight:700;letter-spacing:.03em;color:var(--fg)}
.tlhead span{font-size:11.5px;color:var(--faint);letter-spacing:.02em}
.tl{position:relative;border:1px solid var(--line);border-radius:0;background:var(--track-bg);
overflow:hidden;transition:background .18s}
.tl .g{position:absolute;top:0;bottom:0;width:1px;background:var(--grid-line)}
.tl .day{position:absolute;top:0;bottom:0;border-left:1px solid var(--day-line)}
.tlbar{position:absolute;height:32px;border:1px solid var(--line);border-left:3px solid var(--tc);
border-radius:3px;display:flex;align-items:center;gap:8px;padding:0 10px;overflow:hidden;
background:var(--bar-bg);color:var(--bar-ink);transition:border-color .14s,transform .12s,background .18s}
.tlbar:hover{transform:translateY(-1px);z-index:30;border-color:var(--line-2);border-left-color:var(--tc)}
.tlbar .t{font-size:10.5px;font-weight:700;white-space:nowrap;color:var(--tc);letter-spacing:.04em}
.tlbar .n{flex:1 1 auto;font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;
text-overflow:ellipsis;letter-spacing:.005em}
.tlbar .d{font-size:10.5px;white-space:nowrap;background:var(--pill-bg);border:1px solid var(--pill-bd);
padding:2px 7px;border-radius:3px;color:var(--dim);font-variant-numeric:tabular-nums}
.tlbar .c{font-size:9.5px;font-weight:700;background:transparent;border:1px solid var(--line-2);
padding:1px 5px;border-radius:2px;color:var(--faint);letter-spacing:.06em}
.tlbar .d .cd{font-style:normal;margin-left:8px;padding-left:8px;border-left:1px solid var(--pill-bd);
font-weight:700;color:var(--dim)}
.tlbar .d .cd.soon{color:var(--warn)}
.tlbar .d .cd.over{color:var(--faint);font-weight:500;text-decoration:line-through}
.ticks{position:relative;height:18px;margin-top:6px}
.ticks span{position:absolute;font-size:10.5px;color:var(--faint);transform:translateX(-50%);
font-variant-numeric:tabular-nums}
.nowline{position:absolute;top:0;bottom:0;width:2px;background:var(--red);transform:translateX(-50%);
box-shadow:0 0 10px var(--red-glow);z-index:40;pointer-events:none}

/* ---------- 长期开放 ---------- */
.longterm{margin-top:26px;padding-top:14px;border-top:1px solid var(--line);
display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.longterm b{font-size:11.5px;font-weight:700;color:var(--faint);letter-spacing:.14em;margin-right:4px}
.lt{font-size:11.5px;border:1px solid var(--line);border-left:2px solid var(--tc);border-radius:2px;
padding:4px 10px;background:transparent;color:var(--fg);transition:border-color .14s,background .14s}
.lt:hover{background:color-mix(in srgb,var(--tc) 8%,transparent)}

/* ---------- 图例 ---------- */
.legend{display:flex;flex-wrap:wrap;gap:9px 24px;align-items:center;margin-top:28px;
padding-top:14px;border-top:1px solid var(--line);font-size:11.5px;color:var(--dim)}
.chip2{display:inline-flex;align-items:center;gap:7px;background:transparent;border:0;padding:0;
color:var(--dim);letter-spacing:.02em}
.chip2 b{color:var(--fg);font-weight:700;font-variant-numeric:tabular-nums}
.dot{width:7px;height:7px;border-radius:50%}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}

/* ---------- 页脚 ---------- */
.foot{margin-top:16px;color:var(--faint);font-size:11.5px;line-height:1.95;letter-spacing:.01em}
.foot code{background:var(--code-bg);padding:1px 6px;border-radius:2px;color:var(--code-fg);
font-family:ui-monospace,Consolas,"Courier New",monospace;font-size:11px}
.foot .repolink{color:var(--accent);text-decoration:none;font-weight:600;
border-bottom:1px solid color-mix(in srgb,var(--accent) 40%,transparent)}
.foot .repolink:hover{border-bottom-color:var(--accent)}

/* ---------- 链接态 ---------- */
.go{font-style:normal;font-size:8.5px;line-height:1;opacity:.6;flex:0 0 auto}
a.chip,a.tlbar,a.lt,a.sg{text-decoration:none;cursor:pointer;color:inherit}
a.chip:hover,a.lt:hover,a.tlbar:hover,a.sg:hover{text-decoration:none}
a.tlbar:hover{background:color-mix(in srgb,var(--tc) 6%,var(--bar-bg))}
a.chip:hover .go,a.lt:hover .go,a.tlbar:hover .go,a.sg:hover .go{opacity:1}
"""


def src_attrs(ev):
    """有条目来源 URL 时返回 (href 属性, 标签名)，否则返回 ("", "span")。"""
    u = (ev.get("url") or "").strip()
    if not u:
        return "", "span"
    return (' href="%s" target="_blank" rel="noopener noreferrer"'
            % html.escape(u, quote=True)), "a"


def war_name(ev):
    """卡池短名：取 short 里 " · " 之前的部分，并去掉"复刻"。"""
    s = (ev.get("short") or ev["title"]).split(" · ")[0]
    return s.replace("复刻", "").strip() or s


def load(month_key):
    path = os.path.join(HERE, "hsr_events_%s.json" % month_key)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    if len(argv) >= 2:
        y, m = int(argv[0]), int(argv[1])
    else:
        t = date.today()
        y, m = t.year, t.month
    month_key = "%04d_%02d" % (y, m)
    events = load(month_key)

    m_start = date(y, m, 1)
    m_end = date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)  # 月末
    n_days = (m_end - m_start).days + 1
    pad = m_start.weekday()  # 周一=0
    rows = (pad + n_days + 6) // 7

    now = datetime.now(CST)
    today = now.date()

    # ---- 归一化事件（含 ongoing / 起止解析）----
    items = []
    for ev in events:
        s = date.fromisoformat(ev["date"])
        if ev.get("ongoing"):
            e, ongoing = m_end, True
            s = m_start
        else:
            ongoing = False
            if ev.get("end"):
                e = date.fromisoformat(ev["end"])
            else:
                mm = re.search(r"(\d{1,2})[/\-](\d{1,2})", ev.get("title", ""))
                e = s
                if mm:
                    mo, dy = int(mm.group(1)), int(mm.group(2))
                    for yy in (s.year, s.year + 1):
                        try:
                            cand = date(yy, mo, dy)
                        except ValueError:
                            continue
                        if cand >= s:
                            e = cand
                            break
            if e < s:
                e = s
        items.append({"ev": ev, "start": s, "end": e, "ongoing": ongoing})

    # ---- 网格：每天的“开始”事件与“跨越”事件 ----
    day_start, day_span = {}, {}
    for it in items:
        if it["ongoing"]:
            continue
        day_start.setdefault(it["start"].isoformat(), []).append(it)
        if it["end"] > it["start"]:
            d = it["start"] + timedelta(days=1)
            while d <= it["end"]:
                day_span.setdefault(d.isoformat(), []).append(it)
                d += timedelta(days=1)

    cells = []
    for i in range(rows * 7):
        dnum = i - pad + 1
        if dnum < 1 or dnum > n_days:
            cells.append('<div class="cell pad"></div>')
            continue
        d = date(y, m, dnum)
        key = d.isoformat()
        cls = ["cell"]
        if d.weekday() >= 5:
            cls.append("we")
        if d < today:
            cls.append("past")
        if d == today:
            cls.append("today")
        starts = sorted(day_start.get(key, []), key=lambda x: TYPE_ORDER.get(x["ev"]["type"], 9))
        spans = sorted(day_span.get(key, []), key=lambda x: TYPE_ORDER.get(x["ev"]["type"], 9))
        chips = []
        for it in starts[:3]:
            typ = it["ev"]["type"]
            label, glyph, col = TYPE_META.get(typ, TYPE_META["note"])
            txt = it["ev"].get("short") or it["ev"]["title"][:9]
            if it["end"] > it["start"]:
                txt += " →%d/%d" % (it["end"].month, it["end"].day)
            href, tag = src_attrs(it["ev"])
            chips.append(
                '<%s class="chip%s" style="--tc:%s"%s title="%s">'
                '<span class="ct">%s %s</span>%s</%s>'
                % (tag, " linked" if href else "", col, href,
                   html.escape(it["ev"]["title"]), glyph, html.escape(txt),
                   '<i class="go">\u2197</i>' if href else "", tag)
            )
        if len(starts) > 3:
            chips.append('<span class="more">+%d 项</span>' % (len(starts) - 3))
        # 卡池（war）同日多条合并成一条；全部渲染，超出 4 条折叠
        war_items = [it for it in spans if it["ev"]["type"] == "war"]
        band_list = []          # (标签, 颜色, title, url)
        war_done = False
        for it in spans:
            bev = it["ev"]
            if bev["type"] == "war":
                if war_done:
                    continue
                war_done = True
                if len(war_items) == 1:
                    band_list.append(("卡池：" + war_name(bev),
                                      TYPE_META["war"][2], bev["title"], bev.get("url")))
                else:
                    names = [war_name(x["ev"]) for x in war_items]
                    urls = {x["ev"].get("url") for x in war_items}
                    band_list.append(("卡池：" + "、".join(names), TYPE_META["war"][2],
                                      " / ".join(x["ev"]["title"] for x in war_items),
                                      urls.pop() if len(urls) == 1 else None))
                continue
            band_list.append((bev.get("short") or bev["title"][:6],
                              TYPE_META.get(bev["type"], TYPE_META["note"])[2],
                              bev["title"], bev.get("url")))
        band_parts = []
        for idx, (blabel, bcol, btitle, burl) in enumerate(band_list):
            extra = " extra" if idx >= 4 else ""
            if burl:
                band_parts.append(
                    '<a class="sg linked%s" style="--tc:%s" href="%s"'
                    ' target="_blank" rel="noopener noreferrer" title="%s">'
                    '<span class="sn">%s</span><i class="go">↗</i></a>'
                    % (extra, bcol, html.escape(burl, quote=True),
                       html.escape(btitle), html.escape(blabel)))
            else:
                band_parts.append(
                    '<span class="sg%s" style="--tc:%s" title="%s">'
                    '<span class="sn">%s</span></span>'
                    % (extra, bcol, html.escape(btitle), html.escape(blabel)))
        if len(band_list) > 4:
            band_parts.append(
                '<button class="smore" type="button" data-n="%d">+%d 项</button>'
                % (len(band_list) - 4, len(band_list) - 4))
        band = "".join(band_parts)
        cells.append(
            '<div class="%s" data-date="%s"><div class="dnum">%d</div>'
            '<div class="chips">%s</div><div class="spans">%s</div></div>'
            % (" ".join(cls), key, dnum, "".join(chips), band)
        )

    # ---- 整月时间轴 ----
    def frac(d):
        return (d - m_start).days / float(n_days)

    def frac_end(d):
        return ((d - m_start).days + 1) / float(n_days)

    bars_in = []
    for it in items:
        if it["ongoing"]:
            continue
        s = max(it["start"], m_start)
        e = min(it["end"], m_end)
        if e < s:
            continue
        bars_in.append([frac(s), min(1.0, frac_end(e)), it, s, e])

    def pack(entries):
        out = []
        for it in sorted(entries, key=lambda x: (x[0], -x[1])):
            for row in out:
                if all(it[0] >= o[1] - 0.02 or it[1] <= o[0] + 0.02 for o in row):
                    row.append(it)
                    break
            else:
                out.append([it])
        return out

    rows_packed = pack(bars_in) if bars_in else []
    bars_html = []
    for r, row in enumerate(rows_packed):
        for s_f, e_f, it, s, e in sorted(row, key=lambda x: x[0]):
            ev = it["ev"]
            typ = ev["type"]
            label, glyph, col = TYPE_META.get(typ, TYPE_META["note"])
            mark, sname, sclass = SOURCE_META.get(ev["source"], SOURCE_META["verified"])
            lead = it["start"] < m_start
            tail = it["end"] > m_end
            txt = ev.get("short") or ev["title"][:14]
            dur = "%d/%d~%d/%d" % (it["start"].month, it["start"].day, it["end"].month, it["end"].day)
            if lead and tail:
                dur += " · 两端超出"
            elif tail:
                dur += " · 超出本月"
            elif lead:
                dur += " · 月初前已开"
            href, tag = src_attrs(ev)
            end_ms = int(datetime.combine(it["end"], dtime(23, 59, 59), CST).timestamp() * 1000)
            # 只给数据里真写了 end 的条目加倒计时；单日「点事件」（周常刷新、商店重置等）不加
            cd = ('<i class="cd" data-end="%d"></i>' % end_ms) if ev.get("end") else ""
            bars_html.append(
                '<%s class="tlbar%s" style="left:%.4f%%;width:%.4f%%;top:%dpx;--tc:%s"%s title="%s（至 %s）">'
                '%s<span class="t">%s %s</span>'
                '<span class="n">%s</span><span class="d">%s%s</span>%s%s</%s>'
                % (tag, " linked" if href else "", s_f * 100, max(1.6, (e_f - s_f) * 100),
                   r * ROW_PITCH, col, href, html.escape(ev["title"]), it["end"].isoformat(),
                   '<span class="c">续</span>' if lead else "",
                   glyph, label, html.escape(txt), dur, cd,
                   '<span class="c">续</span>' if tail else "",
                   '<i class="go">\u2197</i>' if href else "", tag)
            )
    tl_h = max(1, len(rows_packed)) * ROW_PITCH + 10

    # ---- 长期开放 ----
    longterm = [it for it in items if it["ongoing"]]
    lt_html = ""
    if longterm:
        lt_parts = []
        for it in longterm:
            lev = it["ev"]
            lmeta = TYPE_META.get(lev["type"], TYPE_META["note"])
            lhref, ltag = src_attrs(lev)
            lt_parts.append(
                '<%s class="lt%s" style="--tc:%s"%s title="%s">%s %s%s</%s>'
                % (ltag, " linked" if lhref else "", lmeta[2], lhref,
                   html.escape(lev["title"]), lmeta[1],
                   html.escape(lev.get("short") or lev["title"][:10]),
                   '<i class="go">\u2197</i>' if lhref else "", ltag))
        chips2 = "".join(lt_parts)
        lt_html = '<div class="longterm"><b>长期开放 / 常驻：</b>%s</div>' % chips2

    # ---- 刻度 & 网格线 ----
    ticks = "".join(
        '<span style="left:%.4f%%">%d</span>' % ((d - 1) / float(n_days) * 100, d)
        for d in range(1, n_days + 1, 2)
    )
    guides = "".join(
        '<i class="g" style="left:%.4f%%"></i>' % ((d - 1) / float(n_days) * 100)
        for d in range(1, n_days + 1, 7)
    )

    # ---- 实时红线：用真实时钟定位（北京时间 UTC+8）----
    start_ms = int(datetime(y, m, 1, tzinfo=CST).timestamp() * 1000)
    span_ms = n_days * 86400000

    n_off = sum(1 for e in events if e["source"] == "official")
    n_ver = sum(1 for e in events if e["source"] == "verified")
    n_dou = sum(1 for e in events if e["source"] == "doubtful")
    clock = now.strftime("%Y-%m-%d %H:%M")

    doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>崩坏：星穹铁道 月历 · @@MONTH@@</title><style>@@CSS@@</style>
<script>@@THEMEJS@@</script></head>
<body>
<button id="themeBtn" class="theme-toggle" type="button" aria-label="切换浅色 / 深色模式" title="切换浅色 / 深色模式"><svg class="tt-sun" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.4v2.6M12 19v2.6M2.4 12h2.6M19 12h2.6M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M18.7 5.3l-1.8 1.8M7.1 16.9l-1.8 1.8"/></svg><svg class="tt-moon" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.5 14.6A8.6 8.6 0 1 1 9.4 3.5a7 7 0 0 0 11.1 11.1z"/></svg><span class="tt-lbl"></span></button>
<div class="frame">
  <div class="head">
    <div class="title">崩坏：星穹铁道 · 月历<span>@@MONTH@@</span></div>
    <div class="meta">每周六刷新<span class="sep">·</span>数据截至 @@CLOCK@@（北京时间）<span class="sep">·</span>今天 <b id="nowtxt">@@TODAY@@</b></div>
  </div>

  <div class="dow">@@DOW@@</div>
  <div class="grid">@@CELLS@@</div>

  <div class="tlwrap">
    <div class="tlhead"><h3>整月时间轴</h3><span>红线 = 当前时刻（按真实时间自动移动）</span></div>
    <div class="tl" style="height:@@TLH@@px">@@GUIDES@@@@BARS@@<i class="nowline" id="nowline"></i></div>
    <div class="ticks">@@TICKS@@</div>
  </div>

  @@LONGTERM@@

  <div class="legend">
    <span class="chip2"><span class="dot" style="background:var(--ok)"></span>官方确认 <b>@@NOFF@@</b></span>
    <span class="chip2"><span class="dot" style="background:var(--warn)"></span>多方印证 <b>@@NVER@@</b></span>
    <span class="chip2"><span class="dot" style="background:var(--bad)"></span>存疑待核 <b>@@NDOU@@</b></span>
    <span class="chip2">事件 <b>@@NEV@@</b> 项<span class="sep">·</span>时间轴 <b>@@NBAR@@</b> 条</span>
  </div>

  <div class="foot">
    覆盖范围 <code>@@MS@@</code> ~ <code>@@ME@@</code>（@@NDAYS@@ 天）· 生成于 @@CLOCK@@（Asia/Shanghai）· 由 <code>hsr_monthly_html.py</code> 生成<br>
    来源：HoYoverse 官方版本更新说明与官方社区发帖、17173 / 4399（公众号官方转载）、TapTap 官方号、GameWith / GameMarket / Notebookcheck 交叉核对。<br>
    🔴 为信源之间日期或名称不一致项；「超出本月」表示该事件在本月结束后仍在持续，请以游戏内公告为准。<br>
    页面地址 <a class="repolink" href="https://ayin.dpdns.org" target="_blank" rel="noopener">ayin.dpdns.org</a>
    · 数据与脚本 <a class="repolink" href="https://github.com/Ayin6667/hsr-calendar" target="_blank" rel="noopener noreferrer">GitHub 仓库 ↗</a>
  </div>
</div>
<script>
(function () {
  var START = @@STARTMS@@, SPAN = @@SPANMS@@, TZ = 8 * 3600 * 1000;
  var line = document.getElementById('nowline');
  var txt = document.getElementById('nowtxt');
  function p2(n) { return (n < 10 ? '0' : '') + n; }
  var cds = document.querySelectorAll('.cd[data-end]');
  function fmtCd(ms) {
    if (ms <= 0) return '已结束';
    var s = Math.floor(ms / 1000), d = Math.floor(s / 86400),
        h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
    if (d > 0) return '剩 ' + d + '天' + (h > 0 ? h + '小时' : '');
    if (h > 0) return '剩 ' + h + '小时' + (m > 0 ? m + '分' : '');
    return '剩 ' + m + '分';
  }
  document.addEventListener('click', function (e) {
    var b = e.target && e.target.closest ? e.target.closest('.smore') : null;
    if (!b) return;
    var cell = b.closest('.cell');
    if (!cell) return;
    var on = cell.classList.toggle('expanded');
    b.textContent = on ? '收起' : ('+' + b.getAttribute('data-n') + ' 项');
  });
  function cdTick(now) {
    for (var i = 0; i < cds.length; i++) {
      var el = cds[i], left = (+el.getAttribute('data-end')) - now;
      var t = fmtCd(left);
      if (el.textContent !== t) el.textContent = t;
      el.className = 'cd' + (left <= 0 ? ' over' : (left < 86400000 ? ' soon' : ''));
    }
  }
  function tick() {
    var t = Date.now();
    var p = (t - START) / SPAN * 100;
    if (p < 0 || p > 100) { line.style.display = 'none'; }
    else { line.style.display = ''; line.style.left = p.toFixed(4) + '%'; }
    var cn = new Date(t + TZ);
    var dstr = (cn.getUTCMonth() + 1) + '/' + cn.getUTCDate();
    if (txt) txt.textContent = dstr + ' 星期' + '@@DOWCHARS@@'.charAt((cn.getUTCDay() + 6) % 7)
      + ' ' + p2(cn.getUTCHours()) + ':' + p2(cn.getUTCMinutes());
    var cell = document.querySelector('.cell.today');
    var want = cn.getUTCFullYear() + '-' + p2(cn.getUTCMonth() + 1) + '-' + p2(cn.getUTCDate());
    if (cell && cell.getAttribute('data-date') !== want) {
      cell.classList.remove('today');
      var nx = document.querySelector('.cell[data-date="' + want + '"]');
      if (nx) nx.classList.add('today');
    }
    cdTick(t);
  }
  tick();
  cdTick(Date.now());
  setInterval(tick, 20000);
})();
</script>
<script>@@TOGGLEJS@@</script>
</body></html>
"""

    repl = {
        "@@CSS@@": CSS,
        "@@MONTH@@": "%d 年 %d 月" % (y, m),
        "@@CLOCK@@": clock,
        "@@TODAY@@": "%d/%d 星期%s %s" % (now.month, now.day, DOW[now.weekday()], now.strftime("%H:%M")),
        "@@DOW@@": "".join(
            '<div class="%s">%s</div>' % ("we" if i >= 5 else "", d) for i, d in enumerate(DOW)
        ),
        "@@CELLS@@": "".join(cells),
        "@@TLH@@": str(tl_h),
        "@@GUIDES@@": guides,
        "@@BARS@@": "".join(bars_html),
        "@@TICKS@@": ticks,
        "@@LONGTERM@@": lt_html,
        "@@NOFF@@": str(n_off), "@@NVER@@": str(n_ver), "@@NDOU@@": str(n_dou),
        "@@NEV@@": str(len(events)), "@@NBAR@@": str(len(bars_in)),
        "@@MS@@": m_start.isoformat(), "@@ME@@": m_end.isoformat(), "@@NDAYS@@": str(n_days),
        "@@STARTMS@@": str(start_ms), "@@SPANMS@@": str(span_ms),
        "@@THEMEJS@@": THEME_JS, "@@TOGGLEJS@@": TOGGLE_JS,
        "@@DOWCHARS@@": "".join(DOW),
    }
    for k, v in repl.items():
        doc = doc.replace(k, v)

    out = os.path.join(HERE, "calendar.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print("WROTE", out, len(doc.encode("utf-8")), "bytes")
    print("MONTH", y, m, "| days", n_days, "| grid rows", rows, "| today", today)
    print("EVENTS", len(events), "| timeline bars", len(bars_in), "| bar rows", len(rows_packed))
    print("ONGOING", len(longterm), "| now", now.strftime("%Y-%m-%d %H:%M"), "CST")


if __name__ == "__main__":
    main()
