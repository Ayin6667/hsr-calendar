#!/usr/bin/env python3
"""Generate an in-game-style HTML activity calendar for Honkai: Star Rail.

Usage:
    python hsr_weekly_html.py YYYY MM DD [--weeks N] [--start YYYY-MM-DD] [--anchor YYYY-MM-DD]

Reads hsr_events_YYYY_MM_DD.json next to this script, writes calendar.html.

Layout mirrors the in-game 活动日历 view:
    * a run of N weeks (default 6) on a Wednesday-based grid
    * one horizontal duration bar per timed event, spanning its real dates
    * a red vertical line marking today

Event duration comes from an explicit "end" field, else parsed from the title
(e.g. 至11/10 15:00, 至11/11 03:59, 持续至9/28, (至11/10 03:59)).
"""
import html
import io
import json
import os
import re
import sys
from datetime import date, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))

TYPE_META = {
    "version": ("版本", "★"),
    "war": ("跃迁", "◆"),
    "light": ("光锥", "◇"),
    "activity": ("活动", "●"),
    "note": ("公告", "■"),
}
SOURCE_META = {
    "official": ("🟢", "官方确认", "ok"),
    "verified": ("🟡", "多方印证", "warn"),
    "doubtful": ("🔴", "存疑待核", "bad"),
}
# 条形配色：[类型, 渐变起, 渐变止, 文字色, 边框色]
BAR_STYLE = {
    "version": ("linear-gradient(90deg,#ff4d6d,#ff8fa3)", "#2a0f18", "#ffd9e1", "#ff7a96"),
    "war":     ("linear-gradient(90deg,#ff8a1f,#ffc457)", "#2a1c05", "#fff2d6", "#ffb347"),
    "light":   ("linear-gradient(90deg,#e8b40f,#ffe680)", "#2a2405", "#fffbe0", "#f2d24b"),
    "activity":("linear-gradient(90deg,#f07a16,#ffb04d)", "#2a1705", "#fff3e0", "#ff9e2c"),
    "note":    ("linear-gradient(90deg,#3f6fd8,#7aa2ff)", "#0d1730", "#e2ebff", "#6f95ff"),
}
NO_END = {
    "war": "至版本结束（11/10）",
    "light": "至版本结束（11/10）",
    "activity": "版本期内",
    "note": "版本期内",
    "version": "版本期内",
}
WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]
ROW_PITCH = 58  # 时间轴每行占用的垂直像素


def parse_end(title):
    """Best-effort extraction of an end date from a Chinese title string."""
    m = re.search(r"(\d{1,2})[/\-](\d{1,2})", title)
    if not m:
        return None
    mo, dy = int(m.group(1)), int(m.group(2))
    if not (1 <= mo <= 12 and 1 <= dy <= 31):
        return None
    return (mo, dy)


def resolve_end(ev, grid_start, grid_end):
    """Return (end_date, is_inferred)."""
    if ev.get("end"):
        try:
            y, m, d = (int(x) for x in str(ev["end"]).split("-"))
            return date(y, m, d), False
        except Exception:
            pass
    parsed = parse_end(ev.get("title", ""))
    start = date.fromisoformat(ev["date"])
    if parsed:
        mo, dy = parsed
        for year in (start.year, start.year + 1):
            try:
                cand = date(year, mo, dy)
            except ValueError:
                continue
            if cand >= start:
                return cand, False
    return start, True


def build_rows(items, eps=0.05):
    """Greedy interval packing; items = [(start_frac, end_frac, payload), ...].

    区间为半开 [start, end)，仅真正重叠（超过 eps）的条目才会换行。
    """
    rows = []
    for it in sorted(items, key=lambda x: (x[0], -x[1])):
        placed = False
        for row in rows:
            if all(it[0] >= o[1] - eps or it[1] <= o[0] + eps for o in row):
                row.append(it)
                placed = True
                break
        if not placed:
            rows.append([it])
    return rows


def main():
    argv = sys.argv[1:]
    nums, weeks, start_override, anchor = [], 6, None, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--weeks":
            i += 1
            weeks = max(1, int(argv[i]))
        elif a.startswith("--weeks="):
            weeks = max(1, int(a.split("=", 1)[1]))
        elif a == "--start":
            i += 1
            start_override = argv[i]
        elif a.startswith("--start="):
            start_override = a.split("=", 1)[1]
        elif a == "--anchor":
            i += 1
            anchor = argv[i]
        elif a.startswith("--anchor="):
            anchor = a.split("=", 1)[1]
        else:
            nums.append(a)
        i += 1

    if len(nums) >= 3:
        y, m, d = int(nums[0]), int(nums[1]), int(nums[2])
    else:
        y, m, d = 2026, 9, 26
    week_start = date(y, m, d)

    data_path = os.path.join(HERE, "hsr_events_%04d_%02d_%02d.json" % (y, m, d))
    with open(data_path, "r", encoding="utf-8") as fh:
        events = json.load(fh)

    today = date.today()

    # ---- grid start: explicit > anchor date's Wednesday > current week - 2 ----
    if start_override:
        grid_start = date.fromisoformat(start_override)
    elif anchor:
        a0 = date.fromisoformat(anchor)
        grid_start = a0 - timedelta(days=(a0.weekday() + 2) % 7)  # 回溯到周三
    else:
        grid_start = today - timedelta(days=(today.weekday() + 2) % 7) - timedelta(weeks=2)
    grid_days = weeks * 7
    grid_end = grid_start + timedelta(days=grid_days - 1)

    # ---- normalize events into timeline items ----
    items, marks, max_end = [], [], grid_start
    for ev in events:
        s = date.fromisoformat(ev["date"])
        e, inferred = resolve_end(ev, grid_start, grid_end)
        if e < s:
            e = s
        max_end = max(max_end, e)
        items.append({"ev": ev, "start": s, "end": e, "inferred": inferred})
    # x 轴固定为 weeks*7 天，超出窗口的事件在末端裁剪并标注
    total_days = grid_days
    beyond = max_end > grid_end

    def frac(dt):
        return (dt - grid_start).days / float(total_days)

    def frac_end(dt):
        # 半开区间：末日 +1 天，使相邻区间（如 10/21 结束 → 10/21 开始）不重叠
        return ((dt - grid_start).days + 1) / float(total_days)

    # 卡池类（跃迁 + 光锥）在游戏里合并显示为一条区间
    pool = [it for it in items if it["ev"]["type"] in ("war", "light")]
    rest = [it for it in items if it["ev"]["type"] not in ("war", "light")]

    bars, group_bars = [], []
    if pool:
        p_start = min(it["start"] for it in pool)
        p_end = max(it["end"] for it in pool)
        group_bars.append(
            [max(0.0, frac(p_start)), min(1.0, frac_end(p_end)), pool, p_start, p_end]
        )
    for it in rest:
        s, e = it["start"], it["end"]
        if e > s:
            bars.append([max(0.0, frac(s)), min(1.0, frac_end(e)), it])
        else:
            marks.append(it)

    rows = build_rows(group_bars + bars) if (group_bars or bars) else []

    # ---- the grid: week header + day ticks ----
    week_head, week_guides = [], []
    for w in range(weeks):
        wstart = grid_start + timedelta(days=w * 7)
        wend = wstart + timedelta(days=6)
        left = (w * 7) / float(total_days) * 100
        width = 7 / float(total_days) * 100
        label = "第%s周" % "一二三四五六七八九十"[w] if w < 10 else "第%d周" % (w + 1)
        week_head.append(
            '<div class="wk" style="left:%.4f%%;width:%.4f%%">'
            '<span class="wk-name">%s</span>'
            '<span class="wk-range">%s ~ %s</span></div>'
            % (left, width, label, wstart.strftime("%m/%d"), wend.strftime("%m/%d"))
        )
        if w:
            week_guides.append('<i class="guide" style="left:%.4f%%"></i>' % left)

    # month labels
    months = []
    seen = set()
    for n in range(total_days):
        dt = grid_start + timedelta(days=n)
        key = (dt.year, dt.month)
        if key not in seen:
            seen.add(key)
            months.append((dt, n / float(total_days) * 100))
    month_html = "".join(
        '<span class="mo" style="left:%.4f%%">%s年%s月</span>' % (p, dt.year, dt.month)
        for dt, p in months
    )

    # ---- today marker ----
    # 红线放进 .track 内部：与时长条共用同一个定位容器，left:X% 精确对齐；
    # ::before 向上延伸穿过月份行与周表头（.sheet-inner 开了 overflow，会被裁掉），
    # 因此把向上延伸的那一段放在 .track 外层不可行，改为整条线就放在 track 里，
    # 只贯穿时间轴本身，视觉上更干净也不会溢出。
    if grid_start <= today <= grid_end:
        tpos = ((today - grid_start).days + 0.5) / float(total_days) * 100
        today_html = (
            '<div class="today-row"><span class="today-flag">今天 %s 星期%s</span></div>'
            % (today.strftime("%m/%d"), WEEKDAYS[today.weekday()])
        )
        today_line_html = '<i class="today-line" style="left:%.4f%%"></i>' % tpos
    else:
        tpos = None
        today_html = (
            '<div class="today-row"><span class="today-flag out">今天 %s 不在窗口内</span></div>'
            % today.strftime("%m/%d")
        )
        today_line_html = ""

    # ---- bars ----
    bar_html = []
    for r, row in enumerate(rows):
        top = r * ROW_PITCH
        for entry in sorted(row, key=lambda x: x[0]):
            if len(entry) == 5:  # 卡池合并条
                s_frac, e_frac, pool, p_start, p_end = entry
                grad, _bg, ink, edge = BAR_STYLE["war"]
                n_off = sum(1 for it in pool if it["ev"]["source"] == "official")
                n_ver = sum(1 for it in pool if it["ev"]["source"] == "verified")
                n_dou = sum(1 for it in pool if it["ev"]["source"] == "doubtful")
                clipped = p_end > grid_end
                title_txt = " / ".join(it["ev"]["title"] for it in pool)
                dur = "%s ~ %s（%d天）" % (p_start.strftime("%m/%d"), p_end.strftime("%m/%d"),
                                          (p_end - p_start).days + 1)
                if clipped:
                    dur += " · 超出窗口"
                titles = [it["ev"]["title"] for it in pool]
                core = re.sub(r"^(活动跃迁|光锥活动跃迁|复刻跃迁|光锥复刻跃迁)", "", titles[0])
                core = core.split("：")[-1].split("；")[0].split("，")[0]
                label_txt = "卡池 %d 项 · %s" % (len(pool), core)
                if len(label_txt) > 60:
                    label_txt = label_txt[:59] + "…"
                bar_html.append(
                    '<div class="bar group" style="left:%.4f%%;width:%.4f%%;top:%dpx;'
                    'background:%s;border-color:%s;color:%s" title="%s">'
                    '<span class="b-type" style="color:%s">◆ 跃迁</span>'
                    '<span class="b-title">%s</span>'
                    '<span class="b-dur">%s</span>'
                    '<span class="b-src src-official">🟢%d</span>'
                    '<span class="b-src src-verified">🟡%d</span>'
                    '<span class="b-src src-doubtful">🔴%d</span>'
                    "</div>"
                    % (s_frac * 100, max(1.0, (e_frac - s_frac) * 100), top, grad, edge, ink,
                       html.escape(title_txt), edge, html.escape(label_txt), dur,
                       n_off, n_ver, n_dou)
                )
                continue
            s_frac, e_frac, it = entry
            ev, e = it["ev"], it["end"]
            typ = ev["type"]
            label, glyph = TYPE_META.get(typ, ("公告", "■"))
            grad, _bg, ink, edge = BAR_STYLE.get(typ, BAR_STYLE["note"])
            mark, sname, sclass = SOURCE_META.get(ev["source"], ("🟡", "多方印证", "warn"))
            clipped = e > grid_end
            width = max(0.9, (e_frac - s_frac) * 100)
            left = s_frac * 100
            days = (e - it["start"]).days + 1
            if clipped:
                dur = "%s ~ %s（%d天）· 超出窗口" % (
                    it["start"].strftime("%m/%d"), e.strftime("%m/%d"), days)
            else:
                dur = "%s ~ %s（%d天）" % (it["start"].strftime("%m/%d"), e.strftime("%m/%d"), days)
            if it.get("week_span"):
                dur += " · 结束时间未确认"
            title_txt = ev["title"]
            if len(title_txt) > 74:
                title_txt = title_txt[:73] + "…"
            title = html.escape(title_txt)
            bar_html.append(
                '<div class="bar" style="left:%.4f%%;width:%.4f%%;top:%dpx;'
                'background:%s;border-color:%s;color:%s" title="%s | %s">'
                '<span class="b-type" style="color:%s">%s %s</span>'
                '<span class="b-title">%s</span>'
                '<span class="b-dur">%s</span>'
                '%s'
                '<span class="b-src src-%s" title="%s">%s</span>'
                "</div>"
                % (left, width, top, grad, edge, ink,
                   html.escape(ev["date"] + " ~ " + e.isoformat()
                               + ("（窗口外延续）" if clipped else "")),
                   html.escape(ev["title"]),
                   edge, glyph, label, title, dur,
                   '<span class="b-cont">续</span>' if clipped else "",
                   sclass, sname, mark)
            )

    # ---- undated single-day markers ----
    mark_html = []
    for it in sorted(marks, key=lambda x: x["start"]):
        ev = it["ev"]
        typ = ev["type"]
        label, glyph = TYPE_META.get(typ, ("公告", "■"))
        _grad, _bg, ink, edge = BAR_STYLE.get(typ, BAR_STYLE["note"])
        mark, sname, sclass = SOURCE_META.get(ev["source"], ("🟡", "多方印证", "warn"))
        left = ((it["start"] - grid_start).days + 0.5) / float(total_days) * 100
        mark_html.append(
            '<div class="mark" style="left:%.4f%%;border-color:%s;color:%s" title="%s">'
            '<span class="m-dot" style="background:%s"></span>'
            '<span class="m-txt">%s %s</span>'
            '<span class="b-src src-%s">%s</span></div>'
            % (left, edge, ink, html.escape(ev["title"]), edge, glyph, html.escape(ev["title"]),
               sclass, mark)
        )

    n_period = len(bars) + len(pool)
    n_point = len(marks)
    n_off = sum(1 for e in events if e["source"] == "official")
    n_ver = sum(1 for e in events if e["source"] == "verified")
    n_dou = sum(1 for e in events if e["source"] == "doubtful")

    version_label = "—"
    for ev in events:
        if ev["type"] == "version":
            mm = re.search(r"v[\d.]+", ev["title"])
            version_label = mm.group(0) if mm else ev["title"][:12]
            break

    rows_px = max(1, len(rows)) * ROW_PITCH + 16
    css = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0b0c10;color:#e9edf5;font-family:"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",system-ui,sans-serif;padding:26px;min-width:1180px}
.frame{position:relative;background:#14161c;border:2px solid #33363f;border-radius:16px;padding:20px 22px 26px;box-shadow:0 0 0 6px #0e1015 inset}
.cal-head{position:relative;display:flex;flex-direction:column;align-items:center;gap:10px;margin:2px 0 16px}
.cal-title{font-size:19px;font-weight:800;color:#e9edf5;white-space:nowrap;text-align:center}
.cal-title span{color:#7e8697;font-size:13px;font-weight:600;margin-left:12px}
.today-row{display:flex;justify-content:center;width:100%}
.today-flag{background:#e33b4e;color:#fff;font-size:16px;font-weight:800;padding:8px 22px;border-radius:9px;white-space:nowrap}
.today-flag.out{background:#3a3f4b;color:#c9cfda}
.today-line{position:absolute;top:0;bottom:0;width:3px;z-index:30;background:#e33b4e;transform:translateX(-50%);box-shadow:0 0 12px #e33b4e99;pointer-events:none}
.today-line::before{content:"";position:absolute;left:50%;bottom:100%;width:3px;height:76px;background:#e33b4e;transform:translateX(-50%);box-shadow:0 0 12px #e33b4e99}
.sheet{position:relative;background:#1b1e25;border:2px solid #3a3e49;border-radius:14px;padding:12px;margin-top:4px}
.sheet-inner{overflow:hidden;border-radius:10px}
.weekbar{position:relative;height:56px;background:linear-gradient(180deg,#2a2d36,#20232b);border:2px solid #474c59;border-radius:10px;overflow:hidden}
.wk{position:absolute;top:0;bottom:0;border-left:2px solid #474c59;padding:6px 0 0 10px}
.wk:first-child{border-left:none}
.wk-name{display:block;font-size:15px;font-weight:800;color:#e9edf5}
.wk-range{display:block;font-size:13px;color:#9aa2b2;margin-top:2px}
.months{position:relative;height:20px;margin:8px 2px 2px}
.mo{position:absolute;font-size:12px;color:#7e8697;transform:translateX(2px)}
.track{position:relative;background:#101218;border:2px solid #3a3e49;border-radius:10px;margin-top:6px;overflow:hidden}
.grid-bg{position:absolute;inset:0;background-image:repeating-linear-gradient(90deg,#ffffff0d 0 1px,transparent 1px 100%);background-size:calc(100%/6) 100%}
.guide{position:absolute;top:0;bottom:0;width:2px;background:#ffffff14}
.bar{position:absolute;height:48px;border:2px solid;border-radius:26px;display:flex;align-items:center;gap:10px;padding:0 16px;min-width:0;overflow:hidden;box-shadow:0 3px 10px #0008;transition:transform .12s,box-shadow .12s}
.bar:hover{transform:translateY(-2px);box-shadow:0 6px 18px #000a;z-index:40}
.b-type{font-size:13px;font-weight:800;white-space:nowrap;opacity:.95}
.b-title{flex:1 1 auto;font-size:14px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.b-dur{font-size:12px;white-space:nowrap;opacity:.88;background:#00000038;padding:3px 9px;border-radius:8px}
.b-src{font-size:12px;white-space:nowrap;background:#00000045;padding:3px 8px;border-radius:8px}
.b-cont{font-size:11px;font-weight:800;white-space:nowrap;background:#ffffff26;border:1px dashed #ffffff66;padding:2px 7px;border-radius:7px;letter-spacing:1px}
.marks{position:relative;margin-top:14px;padding:10px 12px;background:#171a21;border:2px solid #33363f;border-radius:12px}
.marks h3{font-size:14px;color:#9aa2b2;font-weight:700;margin-bottom:10px}
.mark{display:inline-flex;align-items:center;gap:8px;border:2px solid;border-radius:20px;padding:6px 14px;margin:0 10px 10px 0;font-size:13px;background:#1e222b}
.m-dot{width:9px;height:9px;border-radius:50%}
.m-txt{max-width:560px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.legend{display:flex;flex-wrap:wrap;gap:10px 22px;align-items:center;margin-top:18px;padding-top:16px;border-top:2px solid #2b2e37;font-size:13px;color:#9aa2b2}
.legend b{color:#e9edf5}
.chip{display:inline-flex;align-items:center;gap:7px;background:#1e222b;border:2px solid #33363f;border-radius:20px;padding:5px 13px;color:#cfd6e2}
.dot{width:10px;height:10px;border-radius:50%}
.src-official{color:#7ee0a0}.src-verified{color:#f0cd5f}.src-doubtful{color:#fa8a8a}
.foot{margin-top:16px;color:#69707e;font-size:12px;line-height:1.7}
.foot code{background:#1e222b;padding:2px 6px;border-radius:5px;color:#9fb4e8}
"""

    doc = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>崩坏：星穹铁道 活动日历 · %(range)s</title>
<style>%(css)s</style>
</head>
<body>
<div class="frame">
  <div class="cal-head">
    <div class="cal-title">崩坏：星穹铁道 · 活动日历<span>%(version)s 版本 · %(range)s</span></div>
    %(today)s
  </div>

  <div class="sheet">
    <div class="sheet-inner">
      <div class="weekbar">%(weekhead)s</div>
      <div class="months">%(months)s</div>
      <div class="track" style="height:%(track_h)dpx">
        <div class="grid-bg"></div>
        %(guides)s
        %(bars)s
        %(today_line)s
      </div>
    </div>
  </div>

  %(marks)s

  <div class="legend">
    <span class="chip"><span class="dot" style="background:#7ee0a0"></span>🟢 官方确认 <b>%(n_off)d</b></span>
    <span class="chip"><span class="dot" style="background:#f0cd5f"></span>🟡 多方印证 <b>%(n_ver)d</b></span>
    <span class="chip"><span class="dot" style="background:#fa8a8a"></span>🔴 存疑待核 <b>%(n_dou)d</b></span>
    <span class="chip">时长条 <b>%(n_period)d</b> 项 · 单日节点 <b>%(n_point)d</b> 项</span>
  </div>

  <div class="foot">
    时间轴 <code>%(gs)s</code> ~ <code>%(ge)s</code>（%(weeks)d 周 / %(total)d 天）· 红线为今日（%(today_s)s）。<br>
    %(beyond_note)s
    数据来源：HoYoverse 官方版本更新说明与公告、17173（公众号官方转载）、GameWith / GameMarket / Notebookcheck / GameTrader 交叉核对。<br>
    标 🔴 的条目为信源之间名称或时长不一致，请以游戏内公告为准；结束时间标「未确认」的条目由标题文本推断，可能存在偏差。<br>
    生成时间 %(gen)s · 由 <code>hsr_weekly_html.py</code> 生成
  </div>
</div>
</body>
</html>
""" % {
        "range": "%s ~ %s" % (grid_start.isoformat(), grid_end.isoformat()),
        "css": css,
        "version": version_label,
        "today": today_html,
        "today_line": today_line_html,
        "weekhead": "".join(week_head),
        "months": month_html,
        "track_h": rows_px,
        "guides": "".join(week_guides),
        "bars": "".join(bar_html),
        "marks": ('<div class="marks"><h3>单日节点（无跨度）</h3>%s</div>' % "".join(mark_html))
                 if mark_html else "",
        "n_off": n_off, "n_ver": n_ver, "n_dou": n_dou,
        "n_period": n_period, "n_point": n_point,
        "gs": grid_start.isoformat(), "ge": grid_end.isoformat(),
        "weeks": weeks, "total": total_days,
        "today_s": today.isoformat(),
        "gen": today.isoformat(),
        "beyond_note": ("部分事件在 <code>%s</code> 之后仍在持续，已在时间轴末端裁剪并标注「超出窗口」。<br>"
                        % grid_end.isoformat()) if beyond else "",
    }

    out = os.path.join(HERE, "calendar.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print("WROTE", out, len(doc.encode("utf-8")), "bytes")
    print("GRID", grid_start, "~", grid_end, "| days", total_days, "| weeks", weeks)
    print("BARS", n_period, "| ROWS", len(rows), "| POINT-MARKS", n_point)
    print("TODAY", today, "in-window:", grid_start <= today <= grid_end)


if __name__ == "__main__":
    main()
