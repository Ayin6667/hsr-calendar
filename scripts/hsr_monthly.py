#!/usr/bin/env python3
"""Honkai: Star Rail MONTH calendar (月历) — PNG.

Usage: python hsr_monthly.py YYYY MM [DD]

Reads hsr_events_YYYY_MM.json next to this script, writes calendar.png.
Layout: header + 7-column month grid (event chips per day + span bands)
        + full-month timeline with a red "now" line at the real clock time.
"""
import io
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
CST = timezone(timedelta(hours=8))

W = 1620
M = 40                     # 外边距
CELL_H = 148
CELL_GAP = 8
BAR_ROW = 30
TL_TOP_PAD = 34

BG = (13, 15, 28)
PANEL = (25, 28, 50)
PANEL_PAD = (18, 20, 34)
CELL = (25, 28, 46)
CELL_PAST = (20, 22, 36)
CELL_TODAY = (36, 26, 34)
BORDER = (62, 68, 108)
GRIDLINE = (48, 54, 88)
TEXT = (235, 238, 250)
DIM = (158, 166, 198)
FAINT = (112, 120, 152)
ACCENT = (122, 162, 255)
RED = (227, 59, 78)
GOLD = (240, 200, 110)

TYPE_META = {
    "version": ("版本", "★", (255, 77, 109)),
    "war": ("跃迁", "◆", (255, 138, 31)),
    "light": ("光锥", "◇", (232, 180, 15)),
    "activity": ("活动", "●", (47, 191, 113)),
    "note": ("公告", "■", (63, 111, 216)),
}
SOURCE_META = {
    "official": ("[官]", (92, 220, 140), "官方确认"),
    "verified": ("[验]", (240, 205, 95), "多方印证"),
    "doubtful": ("[疑]", (250, 120, 120), "存疑待核"),
}
DOW = ["一", "二", "三", "四", "五", "六", "日"]
FONTS = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc",
         r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc"]


def font(size, bold=False):
    order = ([FONTS[1]] + FONTS) if bold else FONTS
    for p in order:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def clip(dr, text, f, max_w):
    """Trim text with an ellipsis so it fits max_w pixels."""
    if dr.textlength(text, font=f) <= max_w:
        return text
    out = ""
    for ch in text:
        if dr.textlength(out + ch + "…", font=f) > max_w:
            break
        out += ch
    return (out + "…") if out else text[:1]


def wrap(dr, text, f, max_w, max_lines=3):
    lines, cur = [], ""
    for ch in text:
        if dr.textlength(cur + ch, font=f) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines


def normalise(events, m_start, m_end):
    items = []
    for ev in events:
        s = date.fromisoformat(ev["date"])
        if ev.get("ongoing"):
            items.append({"ev": ev, "start": m_start, "end": m_end, "ongoing": True})
            continue
        if ev.get("end"):
            e = date.fromisoformat(ev["end"])
        else:
            e = s
            mm = re.search(r"(\d{1,2})[/\-](\d{1,2})", ev.get("title", ""))
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
        items.append({"ev": ev, "start": s, "end": e, "ongoing": False})
    return items


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


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    if len(argv) >= 2:
        y, m = int(argv[0]), int(argv[1])
    else:
        t = date.today()
        y, m = t.year, t.month
    key = "%04d_%02d" % (y, m)
    with open(os.path.join(HERE, "hsr_events_%s.json" % key), "r", encoding="utf-8") as fh:
        events = json.load(fh)

    m_start = date(y, m, 1)
    m_end = date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)
    n_days = (m_end - m_start).days + 1
    pad = m_start.weekday()
    rows = (pad + n_days + 6) // 7
    now = datetime.now(CST)
    today = now.date()

    items = normalise(events, m_start, m_end)
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

    # ---------- 时间轴排版（先算行数，决定画布高度）----------
    def frac(d):
        return (d - m_start).days / float(n_days)

    def frac_end(d):
        return ((d - m_start).days + 1) / float(n_days)

    bars_in = []
    for it in items:
        if it["ongoing"]:
            continue
        s, e = max(it["start"], m_start), min(it["end"], m_end)
        if e < s:
            continue
        bars_in.append([frac(s), min(1.0, frac_end(e)), it, s, e])
    packed = pack(bars_in) if bars_in else []
    n_bar_rows = max(1, len(packed))

    longterm = [it for it in items if it["ongoing"]]
    lt_h = 62 if longterm else 0

    grid_h = rows * CELL_H + (rows - 1) * CELL_GAP
    head_h = 132
    dow_h = 40
    tl_h = TL_TOP_PAD + n_bar_rows * BAR_ROW + 34
    legend_h = 150
    lt_block = (lt_h + 16) if lt_h else 0
    H = head_h + dow_h + grid_h + 22 + tl_h + 18 + lt_block + legend_h + 26

    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)

    f_title = font(36, True)
    f_sub = font(17)
    f_sec = font(20, True)
    f_dow = font(18, True)
    f_day = font(19, True)
    f_chip = font(13)
    f_tiny = font(12)
    f_badge = font(13, True)

    # ---------------- header ----------------
    dr.rectangle([0, 0, W, head_h], fill=(20, 23, 44))
    dr.rectangle([0, head_h - 4, W, head_h], fill=ACCENT)
    dr.text((M + 6, 22), "崩坏：星穹铁道 · 月历", font=f_title, fill=TEXT)
    dr.text((M + 8, 74),
            "%d 年 %d 月 · 每周六刷新 · 生成于 %s（北京时间）" % (y, m, now.strftime("%Y-%m-%d %H:%M")),
            font=f_sub, fill=ACCENT)
    badge = "今天 %d/%d 星期%s %s" % (now.month, now.day, DOW[now.weekday()], now.strftime("%H:%M"))
    bw = dr.textlength(badge, font=f_sub) + 40
    dr.rounded_rectangle([W - M - bw, 40, W - M, 88], 10, fill=(46, 30, 38), outline=RED, width=2)
    dr.text((W - M - bw + 20, 55), badge, font=f_sub, fill=(255, 160, 172))

    # ---------------- 星期表头 ----------------
    grid_w = W - M * 2
    cw = (grid_w - CELL_GAP * 6) // 7
    top = head_h + 8
    for i, d in enumerate(DOW):
        x = M + i * (cw + CELL_GAP)
        dr.rounded_rectangle([x, top, x + cw, top + dow_h - 8], 8, fill=(32, 35, 43), outline=(58, 62, 73), width=2)
        col = (255, 179, 71) if i >= 5 else DIM
        tw = dr.textlength(d, font=f_dow)
        dr.text((x + (cw - tw) / 2, top + 8), d, font=f_dow, fill=col)
    top += dow_h

    # ---------------- 月网格 ----------------
    for i in range(rows * 7):
        dnum = i - pad + 1
        x = M + (i % 7) * (cw + CELL_GAP)
        yy = top + (i // 7) * (CELL_H + CELL_GAP)
        if dnum < 1 or dnum > n_days:
            dr.rounded_rectangle([x, yy, x + cw, yy + CELL_H], 10, fill=PANEL_PAD, outline=(32, 35, 43), width=2)
            continue
        d = date(y, m, dnum)
        is_today = (d == today)
        fill_c = CELL_TODAY if is_today else (CELL_PAST if d < today else CELL)
        edge = RED if is_today else BORDER
        dr.rounded_rectangle([x, yy, x + cw, yy + CELL_H], 10, fill=fill_c,
                             outline=edge, width=3 if is_today else 2)
        num_col = (255, 107, 125) if is_today else ((255, 179, 71) if d.weekday() >= 5 else (200, 207, 220))
        dr.text((x + 12, yy + 9), str(dnum), font=f_day, fill=num_col)

        cy = yy + 36
        starts = sorted(day_start.get(d.isoformat(), []), key=lambda t: t["ev"]["type"])
        for it in starts[:4]:
            ev = it["ev"]
            label, glyph, col = TYPE_META.get(ev["type"], TYPE_META["note"])
            txt = ev.get("short") or ev["title"][:8]
            if it["end"] > it["start"]:
                txt += "→%d/%d" % (it["end"].month, it["end"].day)
            nm = ev.get("short") or ev["title"][:8]
            lead = "%s %s" % (glyph, nm)
            lead = clip(dr, lead, f_chip, cw - 34)
            dr.rectangle([x + 9, cy + 1, x + 12, cy + 15], fill=col)
            dr.text((x + 17, cy), lead, font=f_chip, fill=col)
            cy += 19
        if len(starts) > 4:
            dr.text((x + 17, cy), "+%d 项" % (len(starts) - 4), font=f_tiny, fill=FAINT)

        spans = sorted(day_span.get(d.isoformat(), []), key=lambda t: t["ev"]["type"])
        by = yy + CELL_H - 6 - min(6, len(spans)) * 4
        for it in spans[:6]:
            col = TYPE_META.get(it["ev"]["type"], TYPE_META["note"])[2]
            dr.rectangle([x + 9, by, x + cw - 9, by + 2], fill=col)
            by += 4

    top += grid_h + 22

    # ---------------- 整月时间轴 ----------------
    dr.rounded_rectangle([M, top, W - M, top + tl_h], 12, fill=(23, 26, 33), outline=(51, 54, 63), width=2)
    dr.text((M + 18, top + 10), "整月时间轴", font=f_sec, fill=TEXT)
    hint = "红线 = 当前时刻（按真实时间定位）"
    dr.text((W - M - 18 - dr.textlength(hint, font=f_tiny), top + 16), hint, font=f_tiny, fill=FAINT)

    tx0, tx1 = M + 18, W - M - 18
    ty0 = top + TL_TOP_PAD
    track_h = n_bar_rows * BAR_ROW
    dr.rectangle([tx0, ty0, tx1, ty0 + track_h], fill=(16, 18, 24), outline=(58, 62, 73), width=2)
    tw = tx1 - tx0
    for d in range(1, n_days + 1, 7):
        gx = tx0 + tw * ((d - 1) / float(n_days))
        dr.line([gx, ty0 + 2, gx, ty0 + track_h - 2], fill=(255, 255, 255, 20), width=1)

    for r, row in enumerate(packed):
        for s_f, e_f, it, s, e in sorted(row, key=lambda t: t[0]):
            ev = it["ev"]
            label, glyph, col = TYPE_META.get(ev["type"], TYPE_META["note"])
            bx0 = tx0 + tw * s_f
            bx1 = tx0 + tw * e_f
            by0 = ty0 + r * BAR_ROW + 3
            by1 = by0 + BAR_ROW - 8
            dr.rounded_rectangle([bx0, by0, bx1, by1], (by1 - by0) // 2,
                                 fill=tuple(int(c * 0.20) for c in col), outline=col, width=2)
            lead = it["start"] < m_start
            tail = it["end"] > m_end
            tag = ("◀" if lead else "") + ("%s %s" % (glyph, ev.get("short") or ev["title"][:10])) + ("▶" if tail else "")
            inner_w = max(10, (bx1 - bx0) - 20)
            dr.text((bx0 + 12, by0 + 5), clip(dr, tag, f_badge, inner_w), font=f_badge, fill=col)

    # 刻度
    tk_y = ty0 + track_h + 8
    for d in range(1, n_days + 1, 2):
        gx = tx0 + tw * ((d - 1) / float(n_days))
        dr.text((gx - 8, tk_y), str(d), font=f_tiny, fill=FAINT)

    # 红线（真实时刻，含日内小数）
    elapsed = (now - now.replace(hour=0, minute=0, second=0, microsecond=0))
    pos = ((now.date() - m_start).days + elapsed.total_seconds() / 86400.0) / float(n_days)
    if 0.0 <= pos <= 1.0:
        nx = tx0 + tw * pos
        dr.line([nx, ty0 - 6, nx, ty0 + track_h + 4], fill=RED, width=3)
        dr.ellipse([nx - 5, ty0 - 11, nx + 5, ty0 - 1], fill=RED)

    top += tl_h + 18

    # ---------------- 长期开放 ----------------
    if longterm:
        dr.rounded_rectangle([M, top, W - M, top + lt_h], 12, fill=(23, 26, 33), outline=(51, 54, 63), width=2)
        dr.text((M + 18, top + 12), "长期开放 / 常驻：", font=f_tiny, fill=DIM)
        lx = M + 168
        for it in longterm:
            col = TYPE_META.get(it["ev"]["type"], TYPE_META["note"])[2]
            t = it["ev"].get("short") or it["ev"]["title"][:10]
            wpx = dr.textlength(t, font=f_tiny) + 22
            if lx + wpx > W - M - 18:
                break
            dr.rounded_rectangle([lx, top + 8, lx + wpx, top + 34], 13, fill=(30, 34, 43), outline=col, width=1)
            dr.text((lx + 11, top + 14), t, font=f_tiny, fill=col)
            lx += wpx + 10
        top += lt_h + 16

    # ---------------- 图例 ----------------
    dr.rounded_rectangle([M, top, W - M, H - 26], 12, fill=(19, 22, 41), outline=BORDER, width=2)
    dr.text((M + 20, top + 14), "信源等级：", font=f_tiny, fill=DIM)
    lx = M + 116
    for k in ("official", "verified", "doubtful"):
        mk, mc, desc = SOURCE_META[k]
        dr.text((lx, top + 14), mk, font=f_badge, fill=mc)
        dr.text((lx + 34, top + 14), desc, font=f_tiny, fill=TEXT)
        lx += 152
    dr.text((M + 590, top + 14), "事件类型：", font=f_tiny, fill=DIM)
    lx = M + 686
    for k, (lb, gl, col) in TYPE_META.items():
        dr.text((lx, top + 14), lb, font=f_tiny, fill=col)
        lx += dr.textlength(lb, font=f_tiny) + 26
    n_off = sum(1 for e in events if e["source"] == "official")
    n_ver = sum(1 for e in events if e["source"] == "verified")
    n_dou = sum(1 for e in events if e["source"] == "doubtful")
    notes = [
        "覆盖 %s ~ %s（%d 天）· 事件 %d 项（🟢%d / 🟡%d / 🔴%d）· 时间轴 %d 条 / %d 行"
        % (m_start.isoformat(), m_end.isoformat(), n_days, len(events), n_off, n_ver, n_dou,
           len(bars_in), n_bar_rows),
        "来源：HoYoverse 官方版本更新说明与官方社区发帖、17173 / 4399（公众号官方转载）、TapTap 官方号、GameWith / GameMarket / Notebookcheck 交叉核对。",
        "红标 [疑] 为信源之间日期或名称不一致项；条带两端的 ◀ ▶ 表示该事件在月初之前已开启 / 月末之后仍在持续，请以游戏内公告为准。",
    ]
    for i, nt in enumerate(notes):
        dr.text((M + 20, top + 42 + i * 24), nt, font=f_tiny, fill=DIM if i < 2 else FAINT)

    out = os.path.join(HERE, "calendar.png")
    img.save(out, "PNG")
    print("WROTE", out, img.size)
    print("MONTH %d %d | days %d | grid rows %d | today %s" % (y, m, n_days, rows, today))
    print("EVENTS %d | bars %d | bar rows %d | canvas %dx%d" % (len(events), len(bars_in), n_bar_rows, W, H))
    print("NOWLINE frac %.5f -> x %.1f (track %.1f..%.1f) total_h %d" % (pos, tx0 + tw * pos, tx0, tx1, H))
    # 自检：内容底部是否超出画布
    if top + 42 + len(notes) * 24 > H - 26:
        print("WARN: 底部文字可能超出画布")
    else:
        print("OK: 版面在画布内")


if __name__ == "__main__":
    main()
