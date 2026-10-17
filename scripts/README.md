# scripts/

《崩坏：星穹铁道》**月历**的生成与归档脚本。

## 文件

| 脚本 | 作用 |
|---|---|
| `hsr_monthly.py` | 读取事件 JSON，用 Pillow 生成月历图 `calendar.png`（月网格 + 整月时间轴） |
| `hsr_monthly_html.py` | 生成同版式的交互式 `calendar.html`，红线按真实时间自动移动 |
| `hsr_upload.py` | 通过 GitHub REST API 把三份产物推到 `YYYY/MM/`，并刷新根目录 `index.html` 落地页与 `README.md` |
| `deploy_cf.py` | 把仓库里的网页产物直传到 Cloudflare Pages（对外站点） |

> **沿革**：本项目原为周历（`hsr_weekly.py` / `hsr_weekly_html.py`，按 `YYYY/Wxx/` 归档）。
> 现已改为**月历 + 每周刷新**：产物落在 `YYYY/MM/`，每周六覆盖刷新当月；旧周历脚本已移除，
> 历史归档 `2026/W38`、`2026/W39`、`2026/W40` 保留。
> 上传脚本原名 `upload_hsr_weekly.py`，因模块名会遮蔽标准库 `os`（`import os` 解析到脚本自身造成循环导入）而更名，请勿改回。

## 依赖

- Python 3，仅 `hsr_monthly.py` 需要 **Pillow**（另两个只用标准库）
- 字体使用 Windows 自带 `msyh.ttc` / `simhei.ttf`，非 Windows 需替换 `FONTS` 列表

## 凭据配置（必做）

凭据**不以明文落在磁盘上**：脚本通过 DSH 的凭据保险库取值，调用

```
node get-secret.mjs <条目名>
```

`get-secret.mjs` 由 `dsh-key-vault` 插件提供（默认位置
`~/.dsh/profiles/<profile>/node_modules/dsh-key-vault/get-secret.mjs`），只把值打到 stdout，
失败时非零退出，脚本据此判断。用到的两个条目：

| 条目名 | 用途 |
|---|---|
| `github.com` | GitHub PAT（`repo` 权限，或对目标仓库的 contents 写权限） |
| `cloudflare.com` | Cloudflare API Token（Account → Cloudflare Pages → Edit）。`account_id` 不是密钥，记在该条目的 notes 里 |

在 DSH 里通过界面钥匙面板或让助手存入即可，脚本侧**不需要任何凭据配置文件**。

### 覆盖顺序（首个命中即用）

`hsr_upload.py`：

1. `--token-file <路径>`
2. 环境变量 `$HSR_GITHUB_TOKEN_FILE` 指向的文件
3. 环境变量 `$GITHUB_TOKEN`
4. 保险库条目 `github.com`（默认）

`deploy_cf.py`：

1. `--creds <路径>`（JSON：`{"api_token": "...", "account_id": "<可选>"}`）
2. 环境变量 `$CLOUDFLARE_CREDS_FILE`
3. 环境变量 `$CLOUDFLARE_API_TOKEN`（可配 `$CLOUDFLARE_ACCOUNT_ID`）
4. 保险库条目 `cloudflare.com`（默认）

> 显式的文件参数**仍然可用**（换机器、临时调试、没有 DSH 环境时用），
> 但**没有任何隐式明文来源会被自动读取**：早先的 `.hsr_token`、
> `%USERPROFILE%\.dsh\secrets\hsr-github-token`、`%USERPROFILE%\.dsh\secrets\cloudflare.json`
> 三个默认路径已全部移除，避免"加密存储 + 明文旁路"绕开保险库。

定位不到 `node` 或 `get-secret.mjs`、或条目不存在时，脚本会在 stderr 打印 `WARN`
并继续尝试后续来源，不会静默成功。

## 用法

```bash
PY=python                              # 或解释器绝对路径

$PY hsr_monthly.py 2026 10             # 生成月历图 calendar.png
$PY hsr_monthly_html.py 2026 10        # 生成月历视图 calendar.html
$PY hsr_upload.py --check-auth         # 自检凭据与仓库可达性
$PY hsr_upload.py 2026 10 --dry-run    # 空跑：只解析路径与提交信息
$PY hsr_upload.py 2026 10              # 正式上传（覆盖刷新当月）
```

环境变量可覆盖目标：`GITHUB_REPO`（默认 `Ayin6667/hsr-calendar`）、`GITHUB_BRANCH`（默认 `main`）。

## 输入数据

两个生成脚本都读取**脚本同目录**下、以年月命名的 `hsr_events_YYYY_MM.json`：

```json
[
  {
    "date": "2026-10-21",
    "end": "2026-11-10",
    "type": "war",
    "title": "4.6 下半跃迁：限定5★千冶·刃（Mortenax Blade，火·虚无）",
    "short": "下半 · 千冶刃",
    "source": "verified",
    "url": "https://gl.ali213.net/html/2026-9/1812903.html"
  }
]
```

- `date` 必填；`end` 可选，用于画时长条
- `type`：`version` | `war` | `light` | `activity` | `note`
- `short` 可选，月网格格子里显示的短标签（缺省则截断标题）
- `url` 可选，该条目的信息源链接；HTML 版会把该条目（月网格 chip / 整月时间轴条 / 常驻胶囊 / 格内色带）渲染成可点击外链（`target="_blank" rel="noopener noreferrer"`）并加 ↗ 标记，缺省则该条目不可点
- `source`：`official` 🟢 | `verified` 🟡 | `doubtful` 🔴
- `ongoing: true` 表示**长期开放 / 常驻**：不计入逐日格子，单独列在「长期开放」一行，
  时间轴按整月铺满

若 `end` 缺失，生成脚本会尝试从 `title` 里解析结束日期（支持 `至11/10 15:00`、`持续至9/28` 等形式）。

`hsr_upload.py` 上传的 `events.json` 与工作用数据内容一致，仅字段顺序规范化。

## 输出路径

```
YYYY/MM/calendar.png     # 月历图
YYYY/MM/calendar.html    # 月历视图（红线按真实时间走动）
YYYY/MM/events.json      # 事件数据
```

**每月一份，每周覆盖刷新**。`calendar.html` 若本地缺失会被跳过，不会导致上传失败。

## 红色「当前时刻」线

- `hsr_monthly.py`：按生成时的真实时刻定位（含日内小数，例如 10-04 20:56 → 12.50%）
- `hsr_monthly_html.py`：除生成时定位外，页面内置脚本每 20 秒按北京时间重算一次，
  页面长时间开着红线也会跟着走；跨零点时「今天」高亮格一并迁移

## 交互特性（仅 HTML 版）

- **色带带名**：月网格每天把跨天条目画成 15px 高的色带，活动名直接显示在色带内；
  同日多个卡池合并为一条 `卡池：A、B`
- **展开更多**：单日超过 4 条时其余折叠为 `+N 项` 按钮，点击就地展开（色带全部预渲染，
  展开只切显隐，不重新请求）
- **结束倒计时**：时间轴上带 `end` 的条目显示 `剩 N天H小时` / `剩 H小时M分` / `剩 M分`，
  结束时标 `已结束`；倒计时与红线共用同一个 20 秒心跳
- **深色/浅色切换**：右上角按钮，选择记在 `localStorage`，首屏渲染前应用以避免闪白；
  未选择时跟随系统 `prefers-color-scheme`

## 部署到 Cloudflare Pages

`deploy_cf.py` 把仓库里的网页产物直传到一个 Cloudflare Pages 项目（不需要构建步骤、不需要 `wrangler.toml`）。

**凭据**：保险库条目 `cloudflare.com`（与 GitHub 的 `github.com` 分开存放），取值顺序见上文「凭据配置」。
`account_id` 不是密钥，按 `$CLOUDFLARE_ACCOUNT_ID` → 保险库条目 notes → 用 token 调 `/accounts` 自动探测
依次解析，因此脚本里不硬编码账号 ID。

> 注意：Cloudflare **账户级** API token 调 `/user/tokens/verify` 会返回 `401 Invalid API Token`，
> 这是**正常现象**（该端点只校验用户级 token）。`deploy_cf.py` 因此改用 `/accounts/...` 端点校验。

```bash
$PY deploy_cf.py --check     # 校验凭据、解析 account_id、确认 Pages 权限
$PY deploy_cf.py --build     # 只装配 ./_site（不需要凭据）
$PY deploy_cf.py             # 装配并部署（首次会自动创建项目）
```

站点内容 = 仓库的 `index.html` + `2026/**`（html/json/png）。装配方式是用 GitHub API 镜像仓库到
`_site/`（raw media type + 重试；`codeload` 的 tarball 接口在本机会被重置连接，故不用），再交给 wrangler 上传。
默认项目名 `hsr-calendar`，可用 `--project` 或 `$CLOUDFLARE_PAGES_PROJECT` 覆盖。

### 自定义域名

Cloudflare Pages 的域名绑定在**控制台或 API** 完成，**不需要仓库里的 `CNAME` 文件**（那是 GitHub Pages 的机制）：

- 域名 DNS 已在 Cloudflare：项目 → Custom domains → 添加，DNS 记录会自动创建
- DNS 在别处：在该处添加 CNAME 指向 `<项目名>.pages.dev`

### 部署产物忽略项

`_site/`、`cloudflare.json`、`*.token` 已在 `.gitignore` 中忽略（防止有人误把手写的文件凭据提交上去）。
