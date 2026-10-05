#!/usr/bin/env python3
"""Deploy the HSR month calendar to Cloudflare Pages (direct upload).

Usage:
    python deploy_cf.py --check           # verify the API token and resolve the account id
    python deploy_cf.py --build           # only assemble ./_site
    python deploy_cf.py                   # assemble ./_site and deploy (default)
    python deploy_cf.py --project <name>  # override the Pages project name

Credentials (first hit wins):
    1. --creds <path>
    2. $CLOUDFLARE_CREDS_FILE
    3. env $CLOUDFLARE_API_TOKEN (+ optional $CLOUDFLARE_ACCOUNT_ID)
    4. %USERPROFILE%\\.dsh\\secrets\\cloudflare.json   {"api_token": "...", "account_id": "..."}
`account_id` is optional: if absent it is resolved from the token via /accounts.
Env overrides: CLOUDFLARE_PAGES_PROJECT (default hsr-calendar).
"""
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "_site")
CF_API = "https://api.cloudflare.com/client/v4"
DEFAULT_PROJECT = os.environ.get("CLOUDFLARE_PAGES_PROJECT", "hsr-calendar")

REPO = os.environ.get("GITHUB_REPO", "Ayin6667/hsr-calendar")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")


def _month_subdir():
    """Current month as YYYY/MM in Beijing time (used only for the local fallback)."""
    from datetime import datetime, timedelta, timezone
    d = datetime.now(timezone(timedelta(hours=8)))
    return "%04d/%02d" % (d.year, d.month)


MONTH_SUBDIR = os.environ.get("HSR_MONTH_SUBDIR") or _month_subdir()

NODE_DIR = r"C:\Users\Ayin\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin"
PNPM = r"C:\Users\Ayin\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\pnpm\bin\pnpm.mjs"


def resolve_creds(cli_path=None):
    cands = []
    if cli_path:
        cands.append((cli_path, "--creds"))
    if os.environ.get("CLOUDFLARE_CREDS_FILE"):
        cands.append((os.environ["CLOUDFLARE_CREDS_FILE"], "$CLOUDFLARE_CREDS_FILE"))
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    cands.append((os.path.join(home, ".dsh", "secrets", "cloudflare.json"),
                  r"%USERPROFILE%\.dsh\secrets\cloudflare.json"))
    for path, label in cands:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                data = json.load(fh)
        except Exception as exc:
            print("ERROR: 无法解析 %s -> %s" % (label, exc))
            return None, None, None
        tok = (data.get("api_token") or data.get("token") or "").strip()
        acc = (data.get("account_id") or "").strip()
        proj = (data.get("project") or DEFAULT_PROJECT).strip()
        if tok:
            print("CREDS  : 已加载（来源：%s）" % path)
            return tok, acc, proj
    if os.environ.get("CLOUDFLARE_API_TOKEN"):
        print("CREDS  : 已加载（来源：$CLOUDFLARE_API_TOKEN）")
        return (os.environ["CLOUDFLARE_API_TOKEN"].strip(),
                os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip(), DEFAULT_PROJECT)
    print("ERROR: 未找到 Cloudflare 凭据。请创建 %USERPROFILE%\\.dsh\\secrets\\cloudflare.json：")
    print('       {"api_token": "<Pages:Edit 权限的 token>", "account_id": "<可选>"}')
    return None, None, None


def cf_get(path, token):
    req = urllib.request.Request(CF_API + path,
                                headers={"Authorization": "Bearer " + token,
                                         "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]


def check(token, account_id):
    """Validate the token against account-level endpoints.

    Note: /user/tokens/verify only accepts USER-owned tokens. Account-owned
    tokens (the usual kind for automation) always return 401 there, so we
    confirm against /accounts/... instead.
    """
    st, body = cf_get("/user/tokens/verify", token)
    if st == 200 and isinstance(body, dict) and body.get("success"):
        print("TOKEN  : 有效（用户级 token, status=%s）" % body.get("result", {}).get("status"))
    else:
        print("TOKEN  : /user/tokens/verify -> http=%s（账户级 token 在此端点报 Invalid 属正常，改用账号端点校验）" % st)

    if not account_id:
        st, body = cf_get("/accounts", token)
        if st == 200 and body.get("success") and body.get("result"):
            accts = body["result"]
            for a in accts:
                print("ACCOUNT: %s (%s)%s" % (a["name"], a["id"],
                                              "  <- 将使用" if len(accts) == 1 else ""))
            if len(accts) > 1:
                print("WARN   : token 可访问多个账号，请在凭据文件写明 account_id")
            account_id = accts[0]["id"]
        else:
            print("ACCOUNT: 无法列出账号 http=%s %s" % (st, str(body)[:160]))
            print("         请把 account_id 写进凭据文件（Cloudflare 控制台右侧栏可见）")
            return None

    st, body = cf_get("/accounts/" + account_id, token)
    if st != 200 or not isinstance(body, dict) or not body.get("success"):
        print("ACCOUNT: %s 不可访问 http=%s %s" % (account_id, st, str(body)[:160]))
        return None
    print("ACCOUNT: %s (%s)" % (body["result"]["name"], account_id))

    st, body = cf_get("/accounts/%s/pages/projects" % account_id, token)
    if st == 200 and isinstance(body, dict) and body.get("success"):
        print("PAGES  : 可访问，现有项目 %d 个" % len(body.get("result") or []))
        return account_id
    print("PAGES  : 不可访问 http=%s %s" % (st, str(body)[:160]))
    print("         请确认 token 权限含 Account -> Cloudflare Pages -> Edit")
    return None


def gh_token():
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"].strip()
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    for p in (os.path.join(home, ".dsh", "secrets", "hsr-github-token"),
              os.path.join(HERE, ".hsr_token")):
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8-sig") as fh:
                t = fh.read().strip()
            if t:
                return t
    return ""


def gh_get(path, token, raw=False):
    """GET a repo API path (or raw file contents)."""
    url = ("https://api.github.com/repos/%s/%s" % (REPO, path)) if not raw else path
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json" if not raw else "application/vnd.github.raw",
        "User-Agent": "dsh-hsr-deploy",
        "X-GitHub-Api-Version": "2022-11-28"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


FALLBACK_INDEX = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>崩坏：星穹铁道 月历</title>
<style>body{min-height:100vh;background:#0b0c10;color:#e9edf5;display:flex;
align-items:center;justify-content:center;font-family:"Microsoft YaHei",system-ui,sans-serif;
padding:32px}.w{background:#14161c;border:2px solid #33363f;border-radius:16px;padding:32px;
max-width:520px;width:100%}h1{font-size:22px;margin-bottom:10px}p{color:#7e8697;font-size:13.5px;
line-height:1.7;margin-bottom:18px}a{display:block;background:#ffc531;color:#1a1c22;font-weight:800;
text-align:center;padding:14px;border-radius:11px;text-decoration:none}</style></head>
<body><div class="w"><h1>崩坏：星穹铁道 · 月历</h1>
<p>正在跳转到当月月历…</p>
<a id="go" href="@@M@@/calendar.html">手动打开</a></div>
<script>(function(){var d=new Date(Date.now()+8*3600*1000),m=d.getUTCMonth()+1;
var s=d.getUTCFullYear()+'/'+(m<10?'0'+m:''+m);var t=s+'/calendar.html';
document.getElementById('go').setAttribute('href',t);
fetch(t,{method:'HEAD'}).then(function(r){if(r.ok)location.replace(t);});})();</script>
</body></html>
"""


def gh_raw(path, token):
    """Download file bytes with the raw media type (no base64 inflation)."""
    req = urllib.request.Request("https://api.github.com/repos/%s/%s" % (REPO, path),
                                headers={"Accept": "application/vnd.github.raw",
                                         "User-Agent": "dsh-hsr-deploy",
                                         "X-GitHub-Api-Version": "2022-11-28"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def build_site():
    """Assemble a publishable folder by mirroring the repo's web assets via the API."""
    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    os.makedirs(SITE)
    token = gh_token()
    n = 0
    total = 0
    try:
        tree = json.loads(gh_get("git/trees/%s?recursive=1" % BRANCH, token).decode())
        wanted = []
        for node in tree.get("tree", []):
            p = node.get("path", "")
            if node.get("type") != "blob":
                continue
            if p == "index.html" or (p.startswith("2026/") and p.lower().endswith(
                    (".html", ".json", ".png", ".css", ".js"))):
                wanted.append(p)
        print("MIRROR : 仓库内待发布文件 %d 个" % len(wanted))
        failed = []
        for p in wanted:
            data = None
            for attempt in range(4):
                try:
                    data = gh_raw("contents/" + p + "?ref=" + BRANCH, token)
                    break
                except Exception as exc:
                    if attempt == 3:
                        failed.append("%s (%s)" % (p, exc))
                    else:
                        import time
                        time.sleep(1.2 * (attempt + 1))
            if data is None:
                continue
            dst = os.path.join(SITE, p)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as out:
                out.write(data)
            n += 1
            total += len(data)
        if failed:
            print("WARN   : %d 个文件下载失败：" % len(failed))
            for f in failed[:5]:
                print("         " + f)
    except Exception as exc:
        print("WARN   : 镜像仓库失败 -> %s" % exc)
        print("WARN   : 退回只发布本地当月文件（%s）" % MONTH_SUBDIR)
        for fn in ("calendar.html", "calendar.png", "events.json"):
            src = os.path.join(HERE, fn)
            if os.path.exists(src):
                dst = os.path.join(SITE, MONTH_SUBDIR, fn)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                n += 1
                total += os.path.getsize(dst)

    idx = os.path.join(SITE, "index.html")
    if not os.path.exists(idx):
        print("WARN   : _site 缺少 index.html，已生成兜底跳转页")
        with open(idx, "w", encoding="utf-8") as fh:
            fh.write(FALLBACK_INDEX.replace("@@M@@", MONTH_SUBDIR))
        n += 1
        total += os.path.getsize(idx)

    if n:
        print("BUILD  : %s  (%d 个文件, %.1f KB)" % (SITE, n, total / 1024.0))
    else:
        print("BUILD  : 没有可发布的文件")
    return n > 0


def run_wrangler(args, token, account_id):
    env = dict(os.environ)
    env["CLOUDFLARE_API_TOKEN"] = token
    env["CLOUDFLARE_ACCOUNT_ID"] = account_id
    env["PATH"] = NODE_DIR + os.pathsep + env.get("PATH", "")
    env["npm_config_yes"] = "true"
    cmd = [os.path.join(NODE_DIR, "node.exe"), PNPM, "dlx", "wrangler@latest"] + args
    print("RUN    : wrangler " + " ".join(args))
    try:
        p = subprocess.run(cmd, env=env, cwd=HERE, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=600)
    except Exception as exc:
        print("ERROR  : 调用 wrangler 失败 -> %s" % exc)
        return 1, ""
    out = (p.stdout or "") + (p.stderr or "")
    for line in out.splitlines():
        if line.strip():
            print("   | " + line.rstrip())
    return p.returncode, out


def main():
    argv = sys.argv[1:]
    token_file, project = None, None
    mode = "deploy"
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--check":
            mode = "check"
        elif a == "--build":
            mode = "build"
        elif a == "--creds":
            i += 1
            token_file = argv[i]
        elif a.startswith("--creds="):
            token_file = a.split("=", 1)[1]
        elif a == "--project":
            i += 1
            project = argv[i]
        elif a.startswith("--project="):
            project = a.split("=", 1)[1]
        i += 1

    if mode == "build":
        return 0 if build_site() else 1

    token, account_id, proj = resolve_creds(token_file)
    if not token:
        return 2
    project = project or proj
    account_id = check(token, account_id or None)
    if not account_id:
        print("RESULT : 凭据不可用")
        return 1

    if mode == "check":
        print("RESULT : 凭据可用，account_id=%s, project=%s" % (account_id, project))
        return 0

    if not build_site():
        print("ERROR  : 没有可发布的文件")
        return 1

    # 首次部署前尝试建项目；已存在会报错，忽略即可
    rc, out = run_wrangler(["pages", "project", "create", project,
                            "--production-branch=main"], token, account_id)
    if rc == 0:
        print("PROJECT: 已创建 %s" % project)
    elif "already exists" in out or "8000002" in out or "duplicate" in out.lower():
        print("PROJECT: %s 已存在，继续部署" % project)
    else:
        print("PROJECT: 创建未成功（可能已存在或无权限），仍尝试部署")

    rc, out = run_wrangler(["pages", "deploy", SITE, "--project-name=" + project,
                            "--branch=main", "--commit-dirty=true"], token, account_id)
    if rc != 0:
        print("ERROR  : 部署失败，退出码 %d" % rc)
        return rc
    url = ""
    for line in out.splitlines():
        if ".pages.dev" in line:
            url = line.strip()
    print("DEPLOYED: %s" % (url or "(见上方 wrangler 输出)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
