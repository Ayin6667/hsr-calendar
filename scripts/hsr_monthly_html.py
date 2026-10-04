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
    "version": ("版本", "★", "#ff4d6d"),
    "war": ("跃迁", "◆", "#ff8a1f"),
    "light": ("光锥", "◇", "#e8b40f"),
    "activity": ("活动", "●", "#2fbf71"),
    "note": ("公告", "■", "#3f6fd8"),
}
SOURCE_META = {
    "official": ("🟢", "官方确认", "ok"),
    "verified": ("🟡", "多方印证", "warn"),
    "doubtful": ("🔴", "存疑待核", "bad"),
}
DOW = ["一", "二", "三", "四", "五", "六", "日"]
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0b0c10;color:#e9edf5;font-family:"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",system-ui,sans-serif;padding:24px;min-width:1420px}
.frame{position:relative;background:#14161c;border:2px solid #33363f;border-radius:16px;padding:20px 22px 24px}
.head{display:flex;flex-direction:column;align-items:center;gap:9px;margin-bottom:16px}
.title{font-size:22px;font-weight:800}
.title span{color:#7e8697;font-size:13px;font-weight:600;margin-left:12px}
.nowbadge{background:#e33b4e;color:#fff;font-size:15px;font-weight:800;padding:7px 20px;border-radius:9px;white-space:nowrap}
.dow{display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-bottom:8px}
.dow div{background:#20232b;border:2px solid #3a3e49;border-radius:8px;text-align:center;padding:7px 0;font-size:14px;font-weight:700;color:#9aa2b2}
.dow div.we{color:#ffb347}
.grid{display:grid;grid-template-columns:repeat(7,1fr);gap:8px}
.cell{position:relative;min-height:118px;background:#191c24;border:2px solid #2f333d;border-radius:10px;padding:7px 8px 9px;display:flex;flex-direction:column;gap:4px}
.cell.pad{background:#12141a;border-color:#20232b}
.cell.past{opacity:.55}
.cell.today{border-color:#e33b4e;box-shadow:0 0 0 2px #e33b4e44 inset;background:#221a1f}
.dnum{font-size:15px;font-weight:800;color:#c8cfdc}
.cell.today .dnum{color:#ff6b7d}
.cell.we .dnum{color:#ffb347}
.dnum small{font-size:11px;color:#6b7382;font-weight:600;margin-left:5px}
.chips{display:flex;flex-direction:column;gap:3px}
.chip{font-size:11.5px;line-height:1.35;padding:2px 6px;border-radius:5px;border-left:3px solid;background:#00000038;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.more{font-size:11px;color:#6b7382}
.spans{margin-top:auto;display:flex;flex-direction:column;gap:2px}
.spans i{display:block;height:3px;border-radius:2px;opacity:.85}
.tlwrap{margin-top:20px;background:#171a21;border:2px solid #33363f;border-radius:12px;padding:14px 16px 18px}
.tlhead{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.tlhead h3{font-size:15px;font-weight:800;color:#e9edf5}
.tlhead span{font-size:12px;color:#7e8697}
.tl{position:relative;border:2px solid #3a3e49;border-radius:8px;background:#101218;overflow:hidden}
.tl .g{position:absolute;top:0;bottom:0;width:1px;background:#ffffff12}
.tl .day{position:absolute;top:0;bottom:0;border-left:1px solid #ffffff0a}
.tlbar{position:absolute;height:38px;border:2px solid;border-radius:20px;display:flex;align-items:center;gap:8px;padding:0 12px;overflow:hidden;box-shadow:0 2px 8px #0007}
.tlbar .t{font-size:11px;font-weight:800;white-space:nowrap}
.tlbar .n{flex:1 1 auto;font-size:12.5px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tlbar .d{font-size:11px;white-space:nowrap;background:#00000042;padding:2px 7px;border-radius:6px;opacity:.9}
.tlbar .c{font-size:10px;font-weight:800;background:#ffffff26;border:1px dashed #ffffff66;padding:1px 5px;border-radius:5px}
.ticks{position:relative;height:18px;margin-top:5px}
.ticks span{position:absolute;font-size:11px;color:#6b7382;transform:translateX(-50%)}
.nowline{position:absolute;top:0;bottom:0;width:3px;background:#e33b4e;transform:translateX(-50%);box-shadow:0 0 12px #e33b4e99;z-index:40;pointer-events:none}
.longterm{margin-top:14px;background:#171a21;border:2px solid #33363f;border-radius:12px;padding:11px 14px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.longterm b{font-size:12.5px;color:#9aa2b2;margin-right:6px}
.lt{font-size:12px;border:1px solid;border-radius:16px;padding:4px 11px;background:#1e222b}
.legend{display:flex;flex-wrap:wrap;gap:9px 20px;align-items:center;margin-top:16px;padding-top:14px;border-top:2px solid #2b2e37;font-size:12.5px;color:#9aa2b2}
.chip2{display:inline-flex;align-items:center;gap:7px;background:#1e222b;border:2px solid #33363f;border-radius:18px;padding:4px 12px;color:#cfd6e2}
.dot{width:10px;height:10px;border-radius:50%}
.ok{color:#7ee0a0}.warn{color:#f0cd5f}.bad{color:#fa8a8a}
.foot{margin-top:14px;color:#69707e;font-size:12px;line-height:1.75}
.foot code{background:#1e222b;padding:2px 6px;border-radius:5px;color:#9fb4e8}
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
                '<span class="chip" style="border-color:%s;color:%s" title="%s">%s %s</span>'
                % (col, col, html.escape(it["ev"]["title"]), glyph, html.escape(txt))
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
                '<div class="tlbar" style="left:%.4f%%;width:%.4f%%;top:%dpx;'
                'background:linear-gradient(180deg,%s33,%s18);border-color:%s;color:#e9edf5" title="%s">'
                '%s<span class="t" style="color:%s">%s %s</span>'
                '<span class="n">%s</span><span class="d">%s</span>%s</div>'
                % (s_f * 100, max(1.6, (e_f - s_f) * 100), r * ROW_PITCH, col, col, col,
                   html.escape(ev["title"]),
                   '<span class="c">续</span>' if lead else "",
                   col, glyph, label, html.escape(txt), dur,
                   '<span class="c">续</span>' if tail else "")
            )
    tl_h = max(1, len(rows_packed)) * ROW_PITCH + 10

    # ---- 长期开放 ----
    longterm = [it for it in items if it["ongoing"]]
    lt_html = ""
    if longterm:
        chips2 = "".join(
            '<span class="lt" style="border-color:%s;color:%s">%s %s</span>'
            % (TYPE_META.get(it["ev"]["type"], TYPE_META["note"])[2],
               TYPE_META.get(it["ev"]["type"], TYPE_META["note"])[2],
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
<title>崩坏：星穹铁道 月历 · @@MONTH@@</title><style>@@CSS@@</style></head>
<body><div class="frame">
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
    <span class="chip2"><span class="dot" style="background:#7ee0a0"></span>🟢 官方确认 <b>@@NOFF@@</b></span>
    <span class="chip2"><span class="dot" style="background:#f0cd5f"></span>🟡 多方印证 <b>@@NVER@@</b></span>
    <span class="chip2"><span class="dot" style="background:#fa8a8a"></span>🔴 存疑待核 <b>@@NDOU@@</b></span>
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
