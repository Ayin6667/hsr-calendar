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
from datetime import date, datetime, timedelta, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
CST = timezone(timedelta(hours=8))
ROW_PITCH = 54

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
  --bg:#0b0c10; --fg:#e9edf5; --dim:#9aa2b2; --faint:#6b7382;
  --frame-bg:#14161c; --frame-bd:#33363f;
  --panel:#171a21; --panel-bd:#33363f;
  --cell-bg:#191c24; --cell-bd:#2f333d; --cell-pad:#12141a; --cell-pad-bd:#20232b;
  --cell-today-bg:#221a1f; --cell-past-op:.55;
  --dow-bg:#20232b; --dow-bd:#3a3e49;
  --track-bg:#101218; --track-bd:#3a3e49;
  --grid-line:rgba(255,255,255,.07); --day-line:rgba(255,255,255,.04);
  --chip-bg:rgba(0,0,0,.22); --pill-bg:rgba(0,0,0,.26); --pill-bd:rgba(255,255,255,.40);
  --divider:#2b2e37; --shadow:rgba(0,0,0,.45);
  --accent:#ffc531; --red:#e33b4e; --red-ink:#ffffff; --red-glow:rgba(227,59,78,.27);
  --weekend:#ffb347; --num:#c8cfdc; --today-num:#ff6b7d;
  --c-version:#ff4d6d; --c-war:#ff8a1f; --c-light:#e8b40f; --c-activity:#2fbf71; --c-note:#3f6fd8;
  --ok:#7ee0a0; --warn:#f0cd5f; --bad:#fa8a8a;
  --bar-bg:#1e222b; --bar-ink:#e9edf5;
  --code-bg:#1e222b; --code-fg:#9fb4e8;
}
[data-theme="light"]{
  --bg:#eef1f7; --fg:#1b1f2a; --dim:#5b6478; --faint:#8b93a7;
  --frame-bg:#ffffff; --frame-bd:#d5dbe6;
  --panel:#f7f9fc; --panel-bd:#dbe1ec;
  --cell-bg:#ffffff; --cell-bd:#e3e8f1; --cell-pad:#f1f4f9; --cell-pad-bd:#e6ebf3;
  --cell-today-bg:#fff2f3; --cell-past-op:.52;
  --dow-bg:#eef2f8; --dow-bd:#d5dbe6;
  --track-bg:#f8fafd; --track-bd:#d5dbe6;
  --grid-line:rgba(0,0,0,.07); --day-line:rgba(0,0,0,.04);
  --chip-bg:rgba(0,0,0,.05); --pill-bg:rgba(255,255,255,.62); --pill-bd:rgba(0,0,0,.18);
  --divider:#e0e5ee; --shadow:rgba(20,30,60,.14);
  --accent:#b07d00; --red:#d92b3f; --red-ink:#ffffff; --red-glow:rgba(217,43,63,.22);
  --weekend:#c2700a; --num:#3a4356; --today-num:#c9183c;
  --c-version:#c9183c; --c-war:#b06400; --c-light:#856a00; --c-activity:#12854a; --c-note:#2a52b0;
  --ok:#12854a; --warn:#8f7200; --bad:#bf2a2a;
  --bar-bg:#ffffff; --bar-ink:#1b1f2a;
  --code-bg:#eef2f8; --code-fg:#2a52b0;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--fg);font-family:"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",system-ui,sans-serif;padding:24px;min-width:1420px;transition:background .18s,color .18s}
.theme-toggle{position:fixed;top:18px;right:18px;z-index:9999;display:inline-flex;align-items:center;gap:8px;background:var(--panel);color:var(--fg);border:2px solid var(--panel-bd);border-radius:22px;padding:8px 15px;font-family:inherit;font-size:13px;font-weight:700;line-height:1;cursor:pointer;box-shadow:0 3px 14px var(--shadow);transition:background .18s,border-color .18s,transform .12s}
.theme-toggle:hover{transform:translateY(-1px);border-color:var(--accent)}
.theme-toggle svg{display:block;flex:0 0 auto}
.tt-moon{display:none}
[data-theme="light"] .tt-sun{display:none}
[data-theme="light"] .tt-moon{display:block}
.tt-lbl::after{content:"浅色"}
[data-theme="light"] .tt-lbl::after{content:"深色"}
.frame{position:relative;background:var(--frame-bg);border:2px solid var(--frame-bd);border-radius:16px;padding:20px 22px 24px;transition:background .18s,border-color .18s}
.head{display:flex;flex-direction:column;align-items:center;gap:9px;margin-bottom:16px}
.title{font-size:22px;font-weight:800}
.title span{color:var(--dim);font-size:13px;font-weight:600;margin-left:12px}
.nowbadge{background:var(--red);color:var(--red-ink);font-size:15px;font-weight:800;padding:7px 20px;border-radius:9px;white-space:nowrap}
.dow{display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-bottom:8px}
.dow div{background:var(--dow-bg);border:2px solid var(--dow-bd);border-radius:8px;text-align:center;padding:7px 0;font-size:14px;font-weight:700;color:var(--dim);transition:background .18s,border-color .18s}
.dow div.we{color:var(--weekend)}
.grid{display:grid;grid-template-columns:repeat(7,1fr);gap:8px}
.cell{position:relative;min-height:118px;background:var(--cell-bg);border:2px solid var(--cell-bd);border-radius:10px;padding:7px 8px 9px;display:flex;flex-direction:column;gap:4px;transition:background .18s,border-color .18s}
.cell.pad{background:var(--cell-pad);border-color:var(--cell-pad-bd)}
.cell.past{opacity:var(--cell-past-op)}
.cell.today{border-color:var(--red);box-shadow:inset 0 0 0 2px var(--red-glow);background:var(--cell-today-bg)}
.dnum{font-size:15px;font-weight:800;color:var(--num)}
.cell.today .dnum{color:var(--today-num)}
.cell.we .dnum{color:var(--weekend)}
.dnum small{font-size:11px;color:var(--faint);font-weight:600;margin-left:5px}
.chips{display:flex;flex-direction:column;gap:3px}
.chip{font-size:11.5px;line-height:1.35;padding:2px 6px;border-radius:5px;border-left:3px solid var(--tc);background:var(--chip-bg);color:var(--tc);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.more{font-size:11px;color:var(--faint)}
.spans{margin-top:auto;display:flex;flex-direction:column;gap:2px}
.spans i{display:block;height:3px;border-radius:2px;opacity:.85}
.tlwrap{margin-top:20px;background:var(--panel);border:2px solid var(--panel-bd);border-radius:12px;padding:14px 16px 18px;transition:background .18s,border-color .18s}
.tlhead{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.tlhead h3{font-size:15px;font-weight:800;color:var(--fg)}
.tlhead span{font-size:12px;color:var(--dim)}
.tl{position:relative;border:2px solid var(--track-bd);border-radius:8px;background:var(--track-bg);overflow:hidden;transition:background .18s,border-color .18s}
.tl .g{position:absolute;top:0;bottom:0;width:1px;background:var(--grid-line)}
.tl .day{position:absolute;top:0;bottom:0;border-left:1px solid var(--day-line)}
.tlbar{position:absolute;height:38px;border:2px solid var(--tc);border-left-width:7px;border-radius:20px;display:flex;align-items:center;gap:8px;padding:0 12px;overflow:hidden;background:var(--bar-bg);color:var(--bar-ink);box-shadow:0 2px 8px var(--shadow);transition:background .18s,transform .12s}
.tlbar:hover{transform:translateY(-1px);z-index:30}
.tlbar .t{font-size:11px;font-weight:800;white-space:nowrap;color:var(--tc)}
.tlbar .n{flex:1 1 auto;font-size:12.5px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tlbar .d{font-size:11px;white-space:nowrap;background:var(--pill-bg);border:1px solid var(--pill-bd);padding:2px 7px;border-radius:6px}
.tlbar .c{font-size:10px;font-weight:800;background:var(--pill-bg);border:1px dashed var(--pill-bd);padding:1px 5px;border-radius:5px}
.ticks{position:relative;height:18px;margin-top:5px}
.ticks span{position:absolute;font-size:11px;color:var(--faint);transform:translateX(-50%)}
.nowline{position:absolute;top:0;bottom:0;width:3px;background:var(--red);transform:translateX(-50%);box-shadow:0 0 12px var(--red);z-index:40;pointer-events:none}
.longterm{margin-top:14px;background:var(--panel);border:2px solid var(--panel-bd);border-radius:12px;padding:11px 14px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;transition:background .18s,border-color .18s}
.longterm b{font-size:12.5px;color:var(--dim);margin-right:6px}
.lt{font-size:12px;border:1px solid var(--tc);border-radius:16px;padding:4px 11px;background:var(--bar-bg);color:var(--tc)}
.legend{display:flex;flex-wrap:wrap;gap:9px 20px;align-items:center;margin-top:16px;padding-top:14px;border-top:2px solid var(--divider);font-size:12.5px;color:var(--dim)}
.chip2{display:inline-flex;align-items:center;gap:7px;background:var(--panel);border:2px solid var(--panel-bd);border-radius:18px;padding:4px 12px;color:var(--fg);transition:background .18s,border-color .18s}
.dot{width:10px;height:10px;border-radius:50%}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}
.foot{margin-top:14px;color:var(--faint);font-size:12px;line-height:1.75}
.foot code{background:var(--code-bg);padding:2px 6px;border-radius:5px;color:var(--code-fg)}
"""


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
        starts = sorted(day_start.get(key, []), key=lambda x: x["ev"]["type"])
        spans = sorted(day_span.get(key, []), key=lambda x: x["ev"]["type"])
        chips = []
        for it in starts[:3]:
            typ = it["ev"]["type"]
            label, glyph, col = TYPE_META.get(typ, TYPE_META["note"])
            txt = it["ev"].get("short") or it["ev"]["title"][:9]
            if it["end"] > it["start"]:
                txt += " →%d/%d" % (it["end"].month, it["end"].day)
            chips.append(
                '<span class="chip" style="--tc:%s" title="%s">%s %s</span>'
                % (col, html.escape(it["ev"]["title"]), glyph, html.escape(txt))
            )
        if len(starts) > 3:
            chips.append('<span class="more">+%d 项</span>' % (len(starts) - 3))
        band = "".join(
            '<i style="background:%s" title="%s"></i>'
            % (TYPE_META.get(it["ev"]["type"], TYPE_META["note"])[2], html.escape(it["ev"]["title"]))
            for it in spans[:6]
        )
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
            bars_html.append(
                '<div class="tlbar" style="left:%.4f%%;width:%.4f%%;top:%dpx;--tc:%s" title="%s">'
                '%s<span class="t">%s %s</span>'
                '<span class="n">%s</span><span class="d">%s</span>%s</div>'
                % (s_f * 100, max(1.6, (e_f - s_f) * 100), r * ROW_PITCH, col,
                   html.escape(ev["title"]),
                   '<span class="c">续</span>' if lead else "",
                   glyph, label, html.escape(txt), dur,
                   '<span class="c">续</span>' if tail else "")
            )
    tl_h = max(1, len(rows_packed)) * ROW_PITCH + 10

    # ---- 长期开放 ----
    longterm = [it for it in items if it["ongoing"]]
    lt_html = ""
    if longterm:
        chips2 = "".join(
            '<span class="lt" style="--tc:%s">%s %s</span>'
            % (TYPE_META.get(it["ev"]["type"], TYPE_META["note"])[2],
               TYPE_META.get(it["ev"]["type"], TYPE_META["note"])[1],
               html.escape(it["ev"].get("short") or it["ev"]["title"][:10]))
            for it in longterm
        )
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
    <div class="title">崩坏：星穹铁道 · 月历<span>@@MONTH@@ · 每周六刷新 · 数据截至 @@CLOCK@@（北京时间）</span></div>
    <div class="nowbadge">今天 <span id="nowtxt">@@TODAY@@</span></div>
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
    <span class="chip2"><span class="dot" style="background:var(--ok)"></span>🟢 官方确认 <b>@@NOFF@@</b></span>
    <span class="chip2"><span class="dot" style="background:var(--warn)"></span>🟡 多方印证 <b>@@NVER@@</b></span>
    <span class="chip2"><span class="dot" style="background:var(--bad)"></span>🔴 存疑待核 <b>@@NDOU@@</b></span>
    <span class="chip2">事件 <b>@@NEV@@</b> 项 · 时间轴 <b>@@NBAR@@</b> 条</span>
  </div>

  <div class="foot">
    覆盖范围 <code>@@MS@@</code> ~ <code>@@ME@@</code>（@@NDAYS@@ 天）· 生成于 @@CLOCK@@（Asia/Shanghai）· 由 <code>hsr_monthly_html.py</code> 生成<br>
    来源：HoYoverse 官方版本更新说明与官方社区发帖、17173 / 4399（公众号官方转载）、TapTap 官方号、GameWith / GameMarket / Notebookcheck 交叉核对。<br>
    🔴 为信源之间日期或名称不一致项；「超出本月」表示该事件在本月结束后仍在持续，请以游戏内公告为准。
  </div>
</div>
<script>
(function () {
  var START = @@STARTMS@@, SPAN = @@SPANMS@@, TZ = 8 * 3600 * 1000;
  var line = document.getElementById('nowline');
  var txt = document.getElementById('nowtxt');
  function p2(n) { return (n < 10 ? '0' : '') + n; }
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
  }
  tick();
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
