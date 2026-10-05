# scripts/

《崩坏：星穹铁道》**月历**的生成与归档脚本。

## 文件

| 脚本 | 作用 |
|---|---|
| `hsr_monthly.py` | 读取事件 JSON，用 Pillow 生成月历图 `calendar.png`（月网格 + 整月时间轴） |
| `hsr_monthly_html.py` | 生成同版式的交互式 `calendar.html`，红线按真实时间自动移动 |
| `hsr_upload.py` | 通过 GitHub REST API 把三份产物推到 `YYYY/MM/` |

> **沿革**：本项目原为周历（`hsr_weekly.py` / `hsr_weekly_html.py`，按 `YYYY/Wxx/` 归档）。
> 现已改为**月历 + 每周刷新**：产物落在 `YYYY/MM/`，每周六覆盖刷新当月；旧周历脚本已移除，
> 历史归档 `2026/W38`、`2026/W39`、`2026/W40` 保留。
> 上传脚本原名 `upload_hsr_weekly.py`，因模块名会遮蔽标准库 `os`（`import os` 解析到脚本自身造成循环导入）而更名，请勿改回。

## 依赖

- Python 3，仅 `hsr_monthly.py` 需要 **Pillow**（另两个只用标准库）
- 字体使用 Windows 自带 `msyh.ttc` / `simhei.ttf`，非 Windows 需替换 `FONTS` 列表

## 凭据配置（必做）

`hsr_upload.py` **不含任何 token**，按序查找（首个命中即用）：

1. `--token-file <路径>`
2. 环境变量 `$HSR_GITHUB_TOKEN_FILE` 指向的文件
3. 环境变量 `$GITHUB_TOKEN`
4. 脚本同目录 `.hsr_token`
5. `%USERPROFILE%\.dsh\secrets\hsr-github-token`（默认，推荐）

创建默认凭据文件（Windows PowerShell）：

```powershell
$dir = Join-Path $env:USERPROFILE '.dsh\secrets'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$file = Join-Path $dir 'hsr-github-token'
# 不要带 BOM、不要带尾随换行
[System.IO.File]::WriteAllText($file, '<你的 token>', (New-Object System.Text.UTF8Encoding($false)))
icacls $file /inheritance:r
icacls $file /grant:r "$($env:USERNAME):(R)"
```

Linux / macOS：

```bash
mkdir -p ~/.dsh/secrets
printf '%s' '<你的 token>' > ~/.dsh/secrets/hsr-github-token
chmod 600 ~/.dsh/secrets/hsr-github-token
```

token 需 `repo` 权限（或对目标仓库的 contents 写权限）。

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
    "date": "2026-10-14",
    "end": "2026-11-04",
    "type": "war",
    "title": "4.6 下半复刻跃迁：限定5★千冶·刃（Mortenax Blade，火·虚无）",
    "short": "下半 · 千冶刃",
    "source": "verified"
  }
]
```

- `date` 必填；`end` 可选，用于画时长条
- `type`：`version` | `war` | `light` | `activity` | `note`
- `short` 可选，月网格格子里显示的短标签（缺省则截断标题）
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

## 部署到 Cloudflare Pages

`deploy_cf.py` 把仓库里的网页产物直传到一个 Cloudflare Pages 项目（不需要构建步骤、不需要 `wrangler.toml`）。

**凭据**（与 GitHub token 分开保存）：`%USERPROFILE%\.dsh\secrets\cloudflare.json`

```json
{"api_token": "<权限：Account -> Cloudflare Pages -> Edit>", "account_id": "<可选，缺省则自动探测>"}
```

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

`_site/` 与 `cloudflare.json` 已在 `.gitignore` 中忽略。
