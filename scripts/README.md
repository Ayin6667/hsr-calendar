# scripts/

《崩坏：星穹铁道》周历的生成与归档脚本。

## 文件

| 脚本 | 作用 |
|---|---|
| `hsr_weekly.py` | 读取事件 JSON，用 Pillow 生成 `calendar.png` |
| `hsr_upload.py` | 通过 GitHub REST API 把 `calendar.png` + `events.json` 推到 `YYYY/Wxx/` |

> 注意：脚本原名 `upload_hsr_weekly.py`，因模块名会遮蔽标准库 `os`（`import os` 会解析到脚本自身导致循环导入）而更名。请勿改回。

## 依赖

- Python 3，仅需 **Pillow**（`hsr_upload.py` 只用标准库）
- 字体使用 Windows 自带 `msyh.ttc` / `simhei.ttf`，非 Windows 需自行替换 `FONT_CANDIDATES`

## 凭据配置（必做）

`hsr_upload.py` **不包含任何 token**，按以下顺序查找（首个命中即用）：

1. `--token-file <路径>`
2. 环境变量 `$HSR_GITHUB_TOKEN_FILE` 指向的文件
3. 环境变量 `$GITHUB_TOKEN`
4. 脚本同目录下的 `.hsr_token`
5. `%USERPROFILE%\.dsh\secrets\hsr-github-token`（默认，推荐）

创建默认凭据文件（PowerShell，Windows）：

```powershell
$dir = Join-Path $env:USERPROFILE '.dsh\secrets'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$file = Join-Path $dir 'hsr-github-token'
# 写入时不要带 BOM、不要带尾随换行
[System.IO.File]::WriteAllText($file, '<你的 token>', (New-Object System.Text.UTF8Encoding($false)))
# 收紧权限：禁用继承，仅保留当前用户可读
icacls $file /inheritance:r
icacls $file /grant:r "$($env:USERNAME):(R)"
```

Linux / macOS：

```bash
mkdir -p ~/.dsh/secrets
printf '%s' '<你的 token>' > ~/.dsh/secrets/hsr-github-token
chmod 600 ~/.dsh/secrets/hsr-github-token
```

token 需要 `repo` 权限（或对目标仓库的 contents 写权限）。

## 用法

```bash
PY=python                # 或你的解释器绝对路径

# 1) 生成图片（参数为 week_start 的年月日，即该周的周六）
$PY hsr_weekly.py 2026 9 26

# 2) 自检凭据与仓库可达性（不写入任何内容）
$PY hsr_upload.py --check-auth

# 3) 空跑：只解析路径、凭据、提交信息
$PY hsr_upload.py 2026 9 26 --dry-run

# 4) 正式上传
$PY hsr_upload.py 2026 9 26
```

环境变量可覆盖目标：`GITHUB_REPO`（默认 `Ayin6667/hsr-calendar`）、`GITHUB_BRANCH`（默认 `main`）。

## 输入数据

`hsr_weekly.py` 读取**脚本同目录**下、以 week_start 命名的 `hsr_events_YYYY_MM_DD.json`：

```json
[
  {"date": "2026-09-28", "type": "version", "title": "v4.6「月升之前，与兽共舞」版本更新上线", "source": "official"}
]
```

- `type`：`version` | `war` | `light` | `activity` | `note`（左上角色标）
- `source`：`official` 🟢 | `verified` 🟡 | `doubtful` 🔴

`hsr_upload.py` 上传的是**同目录**的 `events.json`（仓库格式，缩进 2 空格），
与 `hsr_events_*.json` 内容一致、仅格式不同，需分别生成。

## 输出路径

```
YYYY/Wxx/calendar.png
YYYY/Wxx/events.json
```

`Wxx` 由 week_start 的 ISO 周序号推导（如 2026-09-26 → `2026/W39`）。
