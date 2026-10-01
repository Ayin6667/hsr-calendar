#!/usr/bin/env python3
"""Generate the Honkai: Star Rail weekly calendar image.

Usage: python hsr_weekly.py YYYY MM DD   (DD = week_start, a Saturday)
Reads hsr_events_YYYY_MM_DD.json next to this script, writes calendar.png.
"""
import json
import os
import sys
from datetime import date, timedelta

from PIL import Image, ImageDraw, ImageFont

W = 1600
BG = (13, 15, 28)
PANEL = (25, 28, 50)
PANEL_ALT = (33, 37, 64)
CARD = (22, 25, 45)
BORDER = (62, 68, 108)
TEXT = (235, 238, 250)
DIM = (158, 166, 198)
FAINT = (112, 120, 152)
ACCENT = (122, 162, 255)
GOLD = (240, 200, 110)

TYPE_META = {
    "version": ("版本", (255, 122, 168)),
    "war": ("跃迁", (255, 186, 92)),
    "light": ("光锥", (255, 232, 130)),
    "activity": ("活动", (122, 226, 168)),
    "note": ("公告", (150, 190, 255)),
}
SOURCE_META = {
    "official": ("[官]", (92, 220, 140), "官方确认"),
    "verified": ("[验]", (240, 205, 95), "多方印证"),
    "doubtful": ("[疑]", (250, 120, 120), "存疑待核"),
}

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]


def load_font(size, bold=False):
    order = FONT_CANDIDATES if not bold else [FONT_CANDIDATES[1]] + FONT_CANDIDATES
    for path in order:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def wrap(draw, text, font, max_w):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if draw.textlength(cur + ch, font=font) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def main():
    if len(sys.argv) >= 4:
        y, m, d = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    else:
        y, m, d = 2026, 9, 26
    week_start = date(y, m, d)
    week_end = week_start + timedelta(days=6)

    here = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(here, "hsr_events_%04d_%02d_%02d.json" % (y, m, d))
    with open(data_path, "r", encoding="utf-8") as fh:
        events = json.load(fh)

    by_date = {}
    for ev in events:
        by_date.setdefault(ev["date"], []).append(ev)

    M = 40
    strip_y, strip_h = 168, 128
    det_y = strip_y + strip_h + 22
    pad = 26
    inner_w = W - M * 2 - pad * 2

    # -------- measure (needs a scratch surface) --------
    scratch = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    f_title = load_font(48, bold=True)
    f_sub = load_font(25)
    f_head = load_font(25, bold=True)
    f_day = load_font(27, bold=True)
    f_ev = load_font(19)
    f_badge = load_font(17, bold=True)
    f_small = load_font(17)
    f_tiny = load_font(15)

    groups = [
        ("版本更新 / 剧情", ["version"]),
        ("角色跃迁 & 光锥（卡池）", ["war", "light"]),
        ("活动日历", ["activity"]),
        ("公告 / 时装 / 联动 / 其他", ["note"]),
    ]
    layout = []
    det_h = 132
    for gtitle, types in groups:
        items = [e for e in events if e["type"] in types]
        if not items:
            continue
        layout.append((gtitle, items))
        det_h += 44
        for ev in items:
            lines = wrap(scratch, ev["title"], f_ev, inner_w - 300)
            det_h += max(1, len(lines)) * 25 + 18
        det_h += 12
    det_h += 16

    H = det_y + det_h + 200
    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)

    # ---------------- header ----------------
    dr.rectangle([0, 0, W, 140], fill=(20, 23, 44))
    dr.rectangle([0, 136, W, 140], fill=ACCENT)
    dr.text((M + 8, 26), "崩坏：星穹铁道 · 周历", font=f_title, fill=TEXT)
    dr.text(
        (M + 10, 92),
        "%s（周六） ~ %s（周五）    第 %d 周    ISO W%02d    统计事件 %d 项"
        % (
            week_start.strftime("%Y-%m-%d"),
            week_end.strftime("%Y-%m-%d"),
            week_start.isocalendar()[1],
            week_start.isocalendar()[1],
            len(events),
        ),
        font=f_sub,
        fill=ACCENT,
    )
    ver = next((e for e in events if e["type"] == "version"), None)
    if ver:
        tag = "本周版本：v4.6「月升之前，与兽共舞」"
        tw = dr.textlength(tag, font=f_small)
        dr.rounded_rectangle([W - tw - 78, 48, W - M, 94], 10, fill=(42, 48, 86), outline=GOLD, width=2)
        dr.text((W - tw - 58, 60), tag, font=f_small, fill=GOLD)

    # ---------------- 7-day strip ----------------
    gap = 12
    cw = (W - M * 2 - gap * 6) // 7
    for idx in range(7):
        day = week_start + timedelta(days=idx)
        x = M + idx * (cw + gap)
        day_events = by_date.get(day.isoformat(), [])
        n = len(day_events)
        hot = n > 0
        dr.rounded_rectangle(
            [x, strip_y, x + cw, strip_y + strip_h],
            12,
            fill=PANEL_ALT if hot else PANEL,
            outline=GOLD if hot else BORDER,
            width=3 if hot else 2,
        )
        wd = ["周六", "周日", "周一", "周二", "周三", "周四", "周五"][idx]
        dr.text((x + 16, strip_y + 14), wd, font=f_day, fill=TEXT if hot else DIM)
        dr.text((x + 16, strip_y + 54), day.strftime("%m/%d"), font=f_small, fill=DIM)
        if hot:
            kinds = [TYPE_META.get(e["type"], ("公告", DIM))[1] for e in day_events]
            for i, col in enumerate(kinds[:6]):
                cxp = x + 18 + i * 19
                dr.ellipse([cxp, strip_y + 88, cxp + 12, strip_y + 100], fill=col)
            txt = "%d 项" % n
            dr.text((x + cw - dr.textlength(txt, font=f_tiny) - 16, strip_y + 86), txt, font=f_tiny, fill=GOLD)
        else:
            dr.text((x + 16, strip_y + 86), "无事件", font=f_tiny, fill=FAINT)

    # ---------------- grouped detail panel ----------------
    dr.rounded_rectangle([M, det_y, W - M, det_y + det_h], 16, fill=CARD, outline=BORDER, width=2)
    dr.text((M + pad, det_y + 20), "本周事件明细", font=f_head, fill=TEXT)
    dr.text((M + pad + 200, det_y + 26), "按类型分组 · 标注信源等级与有效期", font=f_tiny, fill=FAINT)

    ry = det_y + 70
    for gtitle, items in layout:
        dr.line([M + pad, ry - 8, W - M - pad, ry - 8], fill=(48, 54, 88), width=1)
        dr.text((M + pad, ry + 2), gtitle, font=f_badge, fill=GOLD)
        ry += 42
        for ev in items:
            label, color = TYPE_META.get(ev["type"], ("公告", DIM))
            mark, mcolor, _ = SOURCE_META.get(ev["source"], ("[验]", DIM, ""))
            bw = dr.textlength(label, font=f_badge) + 16
            dr.rounded_rectangle(
                [M + pad + 4, ry - 2, M + pad + 4 + bw, ry + 22],
                6,
                fill=tuple(int(c * 0.28) for c in color),
            )
            dr.text((M + pad + 12, ry), label, font=f_badge, fill=color)
            dr.text((M + pad + 8 + bw, ry), mark, font=f_badge, fill=mcolor)
            dr.text((M + pad + bw + 46, ry + 1), ev["date"], font=f_tiny, fill=FAINT)
            tx = M + pad + bw + 148
            for i, ln in enumerate(wrap(dr, ev["title"], f_ev, inner_w - (tx - M - pad))):
                dr.text((tx, ry + i * 25), ln, font=f_ev, fill=TEXT)
            ry += max(1, len(wrap(dr, ev["title"], f_ev, inner_w - (tx - M - pad)))) * 25 + 18
        ry += 12

    # ---------------- legend / sources ----------------
    fy = det_y + det_h + 20
    dr.rounded_rectangle([M, fy, W - M, H - 30], 14, fill=(19, 22, 41), outline=BORDER, width=2)
    dr.text((M + 22, fy + 16), "信源等级：", font=f_small, fill=DIM)
    lx2 = M + 132
    for key in ("official", "verified", "doubtful"):
        mark, mcolor, desc = SOURCE_META[key]
        dr.text((lx2, fy + 16), mark, font=f_badge, fill=mcolor)
        dr.text((lx2 + 40, fy + 16), desc, font=f_small, fill=TEXT)
        lx2 += 176
    dr.text((M + 690, fy + 16), "事件类型：", font=f_small, fill=DIM)
    lx2 = M + 810
    for key, (label, color) in TYPE_META.items():
        dr.text((lx2, fy + 16), label, font=f_small, fill=color)
        lx2 += dr.textlength(label, font=f_small) + 34
    notes = [
        "数据来源：HoYoverse 官方 4.6 版本更新说明、17173（公众号官方转载）、GameWith / GameMarket / Notebookcheck / GameTrader 二次信源交叉核对。",
        "红标 [疑]：信源之间名称或持续时长不一致，请以游戏内公告为准。事件按 week_start %s（周六）~ %s（周五）统计。" % (week_start.isoformat(), week_end.isoformat()),
        "生成时间：2026-10-01（Asia/Shanghai）    周历类型：独立会话自动生成    触发计划：每周六 13:00",
    ]
    for i, nt in enumerate(notes):
        dr.text((M + 22, fy + 52 + i * 26), nt, font=f_tiny, fill=DIM if i < 2 else FAINT)

    out = os.path.join(here, "calendar.png")
    img.save(out, "PNG")
    print("WROTE", out, img.size)
    print("EVENTS", len(events))


if __name__ == "__main__":
    main()
