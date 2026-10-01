## 🎮 崩坏:星穹铁道周历

> 每周自动生成 · 版本更新 / 角色跃迁 / 活动日历一览无余

---

### 📌 这是什么？

本仓库归档每周《崩坏:星穹铁道》的关键游戏事件，包括：

- 🆕 **版本更新** — 大版本更新时间与内容（如周中有更新）
- 🎯 **角色跃迁** — 本周角色卡池与光锥信息
- 🎉 **活动日历** — 各类游戏内活动与限时任务
- ✨ **新时装/立绘** — 新发布的外观内容

### 📂 文件结构

```
hsr-calendar/
├── YYYY/
│   └── Wxx/               # YYYY年 第xx周（ISO 周序号）
│       ├── calendar.png    # 本周周历图片
│       └── events.json     # 本周事件数据
├── scripts/
│   ├── hsr_weekly.py       # 周历图片生成
│   ├── hsr_upload.py       # GitHub 上传
│   └── README.md           # 脚本用法与凭据配置
└── README.md
```

`Wxx` 由 week_start（该周周六）的 ISO 周序号推导，例如 `2026-09-26` → `2026/W39`。

### 🔄 更新方式

| 触发时间 | 内容 |
|---------|------|
| 每周六 13:00（北京时间 / Asia/Shanghai） | 生成该周（周六 ~ 下周五）周历并推送到仓库 |

执行由 DSH 会话内的定时提醒驱动，到点自动跑完「搜索事件 → 生成图片 → 上传」全流程。

> 手动执行、凭据配置与依赖说明见 [`scripts/README.md`](scripts/README.md)。
> 上传脚本**不含任何 token**，凭据从本地文件读取（默认 `%USERPROFILE%\.dsh\secrets\hsr-github-token`）。

### 📊 数据来源与标注

信息按以下优先级采集：

- 🟢 **官方确认** — 米哈游 / HoYoverse 官方公告、版本更新说明
- 🟡 **多方印证** — NGA / 百度贴吧 / Bilibili 官方动态 / 官方 Twitter 等交叉核对
- 🔴 **存疑待核** — 信源之间名称或时长不一致（如译名差异），以游戏内公告为准

周历图片右下角附有信源等级图例，`events.json` 中的 `source` 字段为 `official` / `verified` / `doubtful`。

### 🔧 技术栈

- Python 3 + Pillow（周历图片生成）
- GitHub REST API（内容推送，无需 git）
- DSH 会话内定时提醒驱动

### 📝 事件数据字段

```json
[
  {
    "date": "2026-09-28",
    "type": "version",
    "title": "v4.6「月升之前，与兽共舞」版本更新上线",
    "source": "official"
  }
]
```

- `type`：`version` | `war` | `light` | `activity` | `note`
- `source`：`official` | `verified` | `doubtful`

---

*由 [Ayin6667](https://github.com/Ayin6667) 维护 · 周历由 AI 助手自动生成*
