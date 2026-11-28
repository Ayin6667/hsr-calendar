#!/usr/bin/env python3
"""Honkai: Star Rail MONTH calendar (月历) — PNG.

Usage: python hsr_monthly.py YYYY MM [DD]

Reads hsr_events_YYYY_MM.json next to this script, writes calendar.png.

Visual language: minimal editorial / magazine style, matched to the web page.
Backgrounds are flat, no rounded cards; separation is done with 1px hairlines,
event types are carried by text colour rather than coloured blocks.
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
CELL_H = 200
CELL_GAP = 1               # 1px hairline between cells
BAR_ROW = 30
TL_TOP_PAD = 44

# --- palette (dark) — mirrors the web page tokens ---
BG = (13, 14, 17)          # #0d0e11
SURFACE = (19, 20, 24)     # #131418
SURFACE2 = (25, 27, 33)    # #191b21
LINE = (38, 40, 46)        # hairline on dark
LINE2 = (56, 58, 66)
TEXT = (240, 241, 244)
DIM = (152, 157, 168)
FAINT = (108, 113, 124)
ACCENT = (245, 196, 81)    # #f5c451
RED = (255, 93, 108)       # #ff5d6c

TYPE_ORDER = {"version": 0, "war": 1, "light": 2, "activity": 3, "note": 4}

TYPE_META = {
    "version": ("版本", "★", (255, 107, 129)),   # #ff6b81
    "war": ("跃迁", "◆", (255, 159, 67)),        # #ff9f43
    "light": ("光锥", "◇", (232, 197, 71)),      # #e8c547
    "activity": ("活动", "●", (74, 222, 128)),    # #4ade80
    "note": ("公告", "■", (107, 155, 255)),      # #6b9bff
}
SOURCE_META = {
    "official": ("官", (74, 222, 128), "官方确认"),
    "verified": ("验", (232, 197, 71), "多方印证"),
    "doubtful": ("疑", (255, 120, 120), "存疑待核"),
}
DOW = ["一", "二", "三", "四", "五", "六", "日"]
FONTS = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc",
         r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc"]


def mix(col, alpha, base):
    """Composite col over base at the given alpha (0..1)."""
    return tuple(int(round(c * alpha + b * (1 - alpha))) for c, b in zip(col, base))


def font(size, bold=False):
    order = ([FONTS[1]] + FONTS) if bold else FONTS
    for p in order:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def war_name(ev):
    """卡池短名：取 short 里 " · " 之前的部分，并去掉"复刻"。"""
    s = (ev.get("short") or ev["title"]).split(" · ")[0]
    return s.replace("复刻", "").strip() or s


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
    lt_h = 56 if longterm else 0

    grid_h = rows * CELL_H + (rows - 1) * CELL_GAP
    head_h = 132
    dow_h = 44
    tl_h = TL_TOP_PAD + n_bar_rows * BAR_ROW + 36
    legend_h = 150
    lt_block = (lt_h + 20) if lt_h else 0
    H = head_h + dow_h + grid_h + 24 + tl_h + 22 + lt_block + legend_h + 28

    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)

    f_title = font(36, True)
    f_sub = font(16)
    f_month = font(24, True)
    f_sec = font(20, True)
    f_dow = font(16, True)
    f_day = font(19, True)
    f_chip = font(13)
    f_tiny = font(12)
    f_band = font(11)
    f_badge = font(13, True)

    # ---------------- header ----------------
    dr.text((M, 26), "崩坏：星穹铁道 · 月历", font=f_title, fill=TEXT)
    dr.text((M + 2, 82),
            "%d 年 %d 月 · 每周六刷新 · 数据截至 %s（北京时间）" % (y, m, now.strftime("%Y-%m-%d %H:%M")),
            font=f_sub, fill=DIM)
    badge = "今天 %d/%d 星期%s %s" % (now.month, now.day, DOW[now.weekday()], now.strftime("%H:%M"))
    bw = dr.textlength(badge, font=f_sub)
    dr.text((W - M - bw, 44), badge, font=f_sub, fill=RED)
    dr.line([M, head_h - 1, W - M, head_h - 1], fill=LINE2, width=1)

    # ---------------- 星期表头 ----------------
    grid_w = W - M * 2
    cw = (grid_w - CELL_GAP * 6) // 7
    top = head_h + 6
    dr.rectangle([M, top, M + grid_w, top + dow_h - 8], fill=SURFACE2)
    for i, d in enumerate(DOW):
        x = M + i * (cw + CELL_GAP)
        col = (255, 179, 71) if i >= 5 else DIM
        tw = dr.textlength(d, font=f_dow)
        dr.text((x + (cw - tw) / 2, top + 8), d, font=f_dow, fill=col)
    top += dow_h

    # ---------------- 月网格（hairline grid） ----------------
    dr.rectangle([M, top, M + grid_w, top + grid_h], fill=LINE)
    for i in range(rows * 7):
        dnum = i - pad + 1
        x = M + (i % 7) * (cw + CELL_GAP)
        yy = top + (i // 7) * (CELL_H + CELL_GAP)
        if dnum < 1 or dnum > n_days:
            dr.rectangle([x + CELL_GAP, yy + CELL_GAP, x + cw, yy + CELL_H], fill=SURFACE)
            continue
        d = date(y, m, dnum)
        is_today = (d == today)
        bgc = SURFACE2 if is_today else SURFACE
        dr.rectangle([x + CELL_GAP, yy + CELL_GAP, x + cw, yy + CELL_H], fill=bgc)
        if is_today:
            dr.rectangle([x + CELL_GAP, yy + CELL_GAP, x + cw, yy + CELL_GAP + 2], fill=RED)
        num_col = RED if is_today else ((255, 179, 71) if d.weekday() >= 5 else (200, 205, 214))
        dr.text((x + 11, yy + 9), str(dnum), font=f_day, fill=num_col)

        cy = yy + 36
        starts = sorted(day_start.get(d.isoformat(), []),
                        key=lambda t: TYPE_ORDER.get(t["ev"]["type"], 9))
        for it in starts[:3]:
            ev = it["ev"]
            _label, glyph, col = TYPE_META.get(ev["type"], TYPE_META["note"])
            nm = ev.get("short") or ev["title"][:8]
            lead = "%s %s" % (glyph, nm)
            if it["end"] > it["start"]:
                lead += " →%d/%d" % (it["end"].month, it["end"].day)
            lead = clip(dr, lead, f_chip, cw - 24)
            dr.text((x + 11, cy), lead, font=f_chip, fill=col)
            cy += 19
        if len(starts) > 3:
            dr.text((x + 11, cy), "+%d 项" % (len(starts) - 3), font=f_tiny, fill=FAINT)

        spans = sorted(day_span.get(d.isoformat(), []),
                       key=lambda t: TYPE_ORDER.get(t["ev"]["type"], 9))
        # 卡池（war）同日多条合并成一条，与网页版保持一致
        war_items = [it for it in spans if it["ev"]["type"] == "war"]
        bands = []          # (标签, 颜色)
        war_done = False
        for it in spans:
            bev = it["ev"]
            if bev["type"] == "war":
                if war_done:
                    continue
                war_done = True
                if len(war_items) == 1:
                    bands.append(("卡池：" + war_name(bev), TYPE_META["war"][2]))
                else:
                    bands.append(("卡池：" + "、".join(war_name(x["ev"]) for x in war_items),
                                  TYPE_META["war"][2]))
                continue
            bands.append((bev.get("short") or bev["title"][:8],
                          TYPE_META.get(bev["type"], TYPE_META["note"])[2]))
        shown = bands[:4]
        bh, bgap = 15, 2
        block_h = len(shown) * bh + max(0, len(shown) - 1) * bgap
        if len(bands) > 4:
            block_h += 15
        by = yy + CELL_H - 9 - block_h
        for blabel, bcol in shown:
            dr.rectangle([x + 9, by, x + 9 + 3, by + bh], fill=bcol)
            dr.rectangle([x + 12, by, x + cw - 8, by + bh], fill=mix(bcol, 0.14, bgc))
            nm = clip(dr, blabel, f_band, cw - 28)
            dr.text((x + 16, by + 2), nm, font=f_band, fill=TEXT)
            by += bh + bgap
        if len(bands) > 4:
            dr.text((x + 12, by), "+%d 项" % (len(bands) - 4), font=f_tiny, fill=FAINT)

    top += grid_h + 24

    # ---------------- 整月时间轴 ----------------
    dr.text((M, top), "整月时间轴", font=f_sec, fill=TEXT)
    hint = "红线 = 当前时刻（按真实时间定位）"
    dr.text((W - M - dr.textlength(hint, font=f_tiny), top + 6), hint, font=f_tiny, fill=FAINT)
    dr.line([M, top + 34, W - M, top + 34], fill=LINE2, width=1)

    tx0, tx1 = M + 2, W - M - 2
    ty0 = top + TL_TOP_PAD
    track_h = n_bar_rows * BAR_ROW
    dr.rectangle([tx0, ty0, tx1, ty0 + track_h], fill=SURFACE2, outline=LINE, width=1)
    tw = tx1 - tx0
    for d in range(1, n_days + 1, 7):
        gx = tx0 + tw * ((d - 1) / float(n_days))
        dr.line([gx, ty0 + 2, gx, ty0 + track_h - 2], fill=LINE, width=1)

    for r, row in enumerate(packed):
        for s_f, e_f, it, s, e in sorted(row, key=lambda t: t[0]):
            ev = it["ev"]
            _label, glyph, col = TYPE_META.get(ev["type"], TYPE_META["note"])
            bx0 = tx0 + tw * s_f
            bx1 = tx0 + tw * e_f
            by0 = ty0 + r * BAR_ROW + 4
            by1 = by0 + BAR_ROW - 10
            dr.rectangle([bx0, by0, bx0 + 3, by1], fill=col)
            dr.rectangle([bx0 + 3, by0, bx1, by1], fill=mix(col, 0.13, SURFACE2))
            lead = it["start"] < m_start
            tail = it["end"] > m_end
            tag = ("◀" if lead else "") + ("%s %s" % (glyph, ev.get("short") or ev["title"][:10])) + ("▶" if tail else "")
            inner_w = max(10, (bx1 - bx0) - 22)
            dr.text((bx0 + 12, by0 + 4), clip(dr, tag, f_badge, inner_w), font=f_badge, fill=col)

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
        dr.line([nx, ty0 - 8, nx, ty0 + track_h + 4], fill=RED, width=3)
        dr.ellipse([nx - 5, ty0 - 13, nx + 5, ty0 - 3], fill=RED)

    top += tl_h + 22

    # ---------------- 长期开放 ----------------
    if longterm:
        dr.text((M, top + 10), "长期开放 / 常驻", font=f_tiny, fill=DIM)
        dr.line([M, top + lt_h - 8, W - M, top + lt_h - 8], fill=LINE, width=1)
        lx = M + 130
        for it in longterm:
            col = TYPE_META.get(it["ev"]["type"], TYPE_META["note"])[2]
            t = it["ev"].get("short") or it["ev"]["title"][:10]
            wpx = dr.textlength(t, font=f_tiny) + 24
            if lx + wpx > W - M:
                break
            dr.rectangle([lx, top + 9, lx + 3, top + 29], fill=col)
            dr.text((lx + 10, top + 11), t, font=f_tiny, fill=col)
            lx += wpx + 12
        top += lt_h + 20

    # ---------------- 图例 ----------------
    dr.line([M, top, W - M, top], fill=LINE2, width=1)
    dr.text((M, top + 14), "信源等级", font=f_tiny, fill=DIM)
    lx = M + 80
    for k in ("official", "verified", "doubtful"):
        mk, mc, desc = SOURCE_META[k]
        dr.ellipse([lx, top + 18, lx + 7, top + 25], fill=mc)
        dr.text((lx + 13, top + 14), desc, font=f_tiny, fill=TEXT)
        lx += 130
    dr.text((M + 470, top + 14), "事件类型", font=f_tiny, fill=DIM)
    lx = M + 550
    for k, (lb, gl, col) in TYPE_META.items():
        dr.text((lx, top + 14), gl, font=f_tiny, fill=col)
        dr.text((lx + 18, top + 14), lb, font=f_tiny, fill=col)
        lx += dr.textlength(lb, font=f_tiny) + 46
    n_off = sum(1 for e in events if e["source"] == "official")
    n_ver = sum(1 for e in events if e["source"] == "verified")
    n_dou = sum(1 for e in events if e["source"] == "doubtful")
    notes = [
        "覆盖 %s ~ %s（%d 天）· 事件 %d 项（官方 %d / 印证 %d / 存疑 %d）· 时间轴 %d 条 / %d 行"
        % (m_start.isoformat(), m_end.isoformat(), n_days, len(events), n_off, n_ver, n_dou,
           len(bars_in), n_bar_rows),
        "来源：HoYoverse 官方版本更新说明与官方社区发帖、17173 / 4399（公众号官方转载）、TapTap 官方号、Game8 / GameMarket 交叉核对。",
        "存疑项为信源之间日期或名称不一致；条带两端的 ◀ ▶ 表示该事件在月初之前已开启 / 月末之后仍在持续，请以游戏内公告为准。",
    ]
    for i, nt in enumerate(notes):
        dr.text((M, top + 44 + i * 24), nt, font=f_tiny, fill=DIM if i < 2 else FAINT)

    out = os.path.join(HERE, "calendar.png")
    img.save(out, "PNG")
    print("WROTE", out, img.size)
    print("MONTH %d %d | days %d | grid rows %d | today %s" % (y, m, n_days, rows, today))
    print("EVENTS %d | bars %d | bar rows %d | canvas %dx%d" % (len(events), len(bars_in), n_bar_rows, W, H))
    if 0.0 <= pos <= 1.0:
        print("NOWLINE frac %.5f -> x %.1f (track %.1f..%.1f) total_h %d"
              % (pos, tx0 + tw * pos, tx0, tx1, H))
    else:
        print("NOWLINE frac %.5f 不在本月范围内（今天 %s，本月 %s ~ %s），未绘制"
              % (pos, today.isoformat(), m_start.isoformat(), m_end.isoformat()))
    # 自检：内容底部是否超出画布
    if top + 44 + len(notes) * 24 > H - 20:
        print("WARN: 底部文字可能超出画布")
    else:
        print("OK: 版面在画布内")


if __name__ == "__main__":
    main()
