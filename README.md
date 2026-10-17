## 🎮 崩坏:星穹铁道 月历

> **在线查看 → <https://ayin.dpdns.org>**
>
> 每月一份产物 · 每周六刷新当月 · 网页版活动条目可点击跳转官方来源

---

### 🌐 在线地址

| 入口 | 地址 |
|---|---|
| 站点首页（自动跳到当月） | <https://ayin.dpdns.org> |
| 当月月历网页（含实时红线与倒计时） | <https://ayin.dpdns.org/2026/10/calendar.html> |
| 当月月历图片 | <https://ayin.dpdns.org/2026/10/calendar.png> |
| 当月事件数据 | <https://ayin.dpdns.org/2026/10/events.json> |

站点由 Cloudflare Pages 托管，自定义域名 `ayin.dpdns.org` 绑定在项目 `hsr-calendar` 上。本仓库是同一个站点的内容源，**日常请直接看在线地址**——网页版比图片多了实时红线、结束倒计时、浅色/深色切换和可点击来源。

### 📌 这是什么？

按月归档《崩坏:星穹铁道》的关键游戏事件，覆盖整月而非单周：

- 🆕 **版本期** — 大版本起止与上下半切换
- 🎯 **角色跃迁** — 卡池、专武、复刻时间窗
- 🎉 **活动日历** — 版本活动、限时双倍、常驻轮换
- ✨ **新时装 / 公告** — 外观上架与重要官方公告

### 📂 文件结构

```
hsr-calendar/
├── index.html              # 站点首页（按北京时间自动跳转到当月）
├── 404.html                # 未知路径的自定义 404 页（缺了它未知路径会回退首页并返回 200）
├── YYYY/
│   └── MM/                 # 年/月，每月一份产物，每周覆盖刷新
│       ├── calendar.png    # 月历图片（月网格 + 整月时间轴）
│       ├── calendar.html   # 月历网页（实时红线 / 倒计时 / 主题切换 / 来源外链）
│       └── events.json     # 当月事件数据
├── scripts/
│   ├── hsr_monthly.py          # 月历图片生成（Pillow）
│   ├── hsr_monthly_html.py     # 月历网页生成
│   ├── hsr_upload.py           # 上传 GitHub、刷新首页与 404 页
│   ├── deploy_cf.py            # 部署 Cloudflare Pages
│   └── README.md               # 脚本用法与凭据配置
└── README.md
```

### 🔄 更新方式

| 触发时间 | 内容 |
|---|---|
| 每周六 13:00（北京时间 / Asia/Shanghai） | 检索当月事件 → 重新生成图片与网页 → 覆盖上传当月目录 → 部署站点 |

**月历每月换新、每周刷新**：同一个月份目录每周被覆盖一次，所以月中随时打开都是最新排期。跨月时自动写入新月份目录。

执行由 DSH 会话内的定时提醒驱动，全流程无人值守。

### ✨ 网页版特性

- **实时红线** — 按真实时刻（含日内小数）定位，页面内每 20 秒自行走动，不随刷新冻结
- **结束倒计时** — 每条有明确结束时间的活动，在时长标签内显示「剩 N天H小时」，24 小时内转为橙色告警，过期显示删除线
- **条目即链接** — 月网格彩线、整月时间轴条、常驻胶囊均可点击，直达官方公告（新标签页打开）
- **卡池合并** — 同日多个卡池在网格中合并为一条（如「卡池 真珠+绯英」），详情见下方时间轴
- **展开更多** — 单日事件较多时显示「+N 项」，点击展开该格全部条目
- **浅色 / 深色** — 跟随系统偏好，可手动切换并记住选择

### 📊 数据来源与标注

信息按以下优先级采集：

| 优先 | 来源 |
|---|---|
| 1 | 米游社 · 崩坏：星穹铁道「官方 → 公告」 |
| 2 | HoYoverse 官方版本更新说明 |
| 3 | Bilibili 崩坏星穹铁道官方 |
| 4 | TapTap 官方号 |
| 兜底 | 以上均无对应内容时，回退到可核查的精确来源（游侠网 / GameMarket / Fandom 等），避免挂无关页面凑数 |

`source` 字段含义：

- 🟢 `official` — 官方公告直接确认
- 🟡 `verified` — 多方印证或官方间接说明
- 🔴 `doubtful` — 信源之间日期或名称不一致，以游戏内公告为准

### 📝 事件数据字段

```json
[
  {
    "date": "2026-10-12",
    "end": "2026-10-25",
    "type": "activity",
    "url": "https://www.miyoushe.com/sr/article/78837137",
    "title": "「位面分裂」位面饰品限时双倍掉落（10/12–10/25）",
    "short": "位面分裂",
    "source": "verified"
  }
]
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `date` | ✅ | 开始日 `YYYY-MM-DD` |
| `end` | | 结束日；有跨度就填，用于画时长条与倒计时 |
| `type` | ✅ | `version` / `war` / `light` / `activity` / `note` |
| `url` | | 信息源链接；网页版会渲染为可点击外链 |
| `title` | ✅ | 完整标题 |
| `short` | | 月网格与彩线里的短标签（缺省截断标题） |
| `source` | ✅ | `official` / `verified` / `doubtful` |
| `ongoing` | | `true` 表示长期开放 / 常驻，单独归入「长期开放」一行 |

### 🔧 技术栈

- Python 3 + Pillow（月历图片）
- 纯静态 HTML/CSS/JS（无框架、无构建、无外部请求）
- GitHub REST API（内容推送，无需 git）；Cloudflare Pages（托管与自定义域名）
- DSH 会话内定时提醒驱动

> 手动执行、凭据配置与依赖说明见 [`scripts/README.md`](scripts/README.md)。
> 脚本**不含任何凭据**，统一通过 DSH 保险库取值（`dsh-key-vault/get-secret.mjs` 的 `github.com` 与 `cloudflare.com` 两个条目），
> 磁盘上不保留明文副本。需要临时覆盖时用 `--token-file` / `--creds` 或 `$GITHUB_TOKEN` / `$CLOUDFLARE_API_TOKEN`。

---

*在线站点 <https://ayin.dpdns.org> · 由 [Ayin6667](https://github.com/Ayin6667) 维护 · 月历由 AI 助手自动生成*
