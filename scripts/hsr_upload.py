#!/usr/bin/env python3
"""Upload the HSR month calendar + events to the GitHub archive repo.

Usage:
    python hsr_upload.py YYYY MM               # upload/refresh that month
    python hsr_upload.py YYYY MM --dry-run     # resolve paths + token, print, upload nothing
    python hsr_upload.py --check-auth          # verify the token only

One file set per month under YYYY/MM/, overwritten on every weekly run.

Token resolution order (first hit wins):
    1. --token-file <path>              (explicit override)
    2. $HSR_GITHUB_TOKEN_FILE           (explicit override)
    3. $GITHUB_TOKEN                    (env var wins over the vault)
    4. dsh-key-vault entry "github.com" (the normal path)

No implicit plaintext token file is read any more: the token comes from the vault
through get-secret.mjs, so no second copy of the secret sits on disk.
Env overrides: GITHUB_REPO (default Ayin6667/hsr-calendar), GITHUB_BRANCH (default main).
"""
import base64
import glob
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO = os.environ.get("GITHUB_REPO", "Ayin6667/hsr-calendar")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")
API = "https://api.github.com/repos/" + REPO
HERE = os.path.dirname(os.path.abspath(__file__))

TOKEN_TERMS = [
    "ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_", "-----BEGIN",
]


# --------------------------------------------------------------------------- #
# Credential source: dsh-key-vault CLI
#
# Every read goes through get-secret.mjs, which prints just the value on stdout
# and exits non-zero on any failure. The vault is the single source, so no
# plaintext copy of the token is kept on disk. An explicit --token-file (or the
# matching env var) still wins, so a one-off override stays possible.
# --------------------------------------------------------------------------- #
VAULT_ENTRY_GITHUB = "github.com"


def _first_existing(cands):
    for cand in cands:
        if cand and os.path.exists(cand):
            return cand
    return None


def _node_exe():
    """Locate node.exe, which is only needed to run the vault CLI."""
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    cands = [os.environ.get("DSH_NODE"), shutil.which("node"), shutil.which("node.exe")]
    cands += sorted(glob.glob(os.path.join(home, ".dsh", "dsh-runtimes", "*",
                                           "dependencies", "node", "bin", "node.exe")))
    return _first_existing(cands)


def _vault_cli():
    """Locate get-secret.mjs from the installed dsh-key-vault plugin."""
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    cands = [os.environ.get("HSR_VAULT_CLI"), os.environ.get("DSH_KEY_VAULT_CLI")]
    cands += sorted(glob.glob(os.path.join(home, ".dsh", "profiles", "*", "node_modules",
                                           "dsh-key-vault", "get-secret.mjs")))
    p = _first_existing(cands)
    # node_modules\dsh-key-vault 是 pnpm 软链接：把链接路径当 argv[1] 传给 node 时，
    # get-secret.mjs 的入口判断 import.meta.url !== argv[1] 会失败，主流程静默跳过，
    # 输出为空且退出码 0。realpath 解引用到真实路径后两者一致。
    return os.path.realpath(p) if p else None


def vault_get(name, field="secret", purpose="hsr-calendar 月历站点自动发布"):
    """Return one field of a vault entry, or None when the vault is unavailable."""
    cli, node = _vault_cli(), _node_exe()
    if not cli or not node:
        print("WARN   : 保险库不可用（node=%s cli=%s）"
              % ("找到" if node else "未找到", cli or "未找到"), file=sys.stderr)
        return None
    try:
        proc = subprocess.run([node, cli, name, "--purpose", purpose, "--field", field],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=30)
    except Exception as exc:
        print("WARN   : 调用保险库失败 -> %s" % exc, file=sys.stderr)
        return None
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip() or ("exit %s" % proc.returncode)
        print("WARN   : 保险库读取 %s 失败 -> %s" % (name, detail), file=sys.stderr)
        return None
    return (proc.stdout or "").strip() or None


def resolve_token(cli_file=None):
    """Return (token, source_description)."""
    explicit = []
    if cli_file:
        explicit.append((cli_file, "--token-file"))
    if os.environ.get("HSR_GITHUB_TOKEN_FILE"):
        explicit.append((os.environ["HSR_GITHUB_TOKEN_FILE"], "$HSR_GITHUB_TOKEN_FILE"))
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"].strip(), "$GITHUB_TOKEN (环境变量)"
    problems = []
    for path, label in explicit:
        if not os.path.exists(path):
            problems.append("  未找到: " + label + "\n            " + path)
            continue
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                token = fh.read().strip()
        except OSError as exc:
            problems.append("  读取失败: " + label + " -> " + str(exc))
            continue
        if not token:
            problems.append("  文件为空: " + label + " -> " + path)
            continue
        if not token.startswith(tuple(TOKEN_TERMS)):
            problems.append("  内容不像 GitHub token（应以 ghp_/github_pat_ 等开头）: " + label)
            continue
        return token, label + "\n           " + path
    token = vault_get(VAULT_ENTRY_GITHUB)
    if token:
        if token.startswith(tuple(TOKEN_TERMS)):
            return token, "dsh-key-vault 条目 " + VAULT_ENTRY_GITHUB
        problems.append("  保险库条目 %s 的内容不像 GitHub token" % VAULT_ENTRY_GITHUB)
    print("ERROR: 未找到可用的 GitHub token。"
          "可用 --token-file 指定，或把 token 存进保险库条目 %s。" % VAULT_ENTRY_GITHUB)
    for p in problems:
        print(p)
    return None, None


def request(url, token, method="GET", payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "dsh-hsr-weekly")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:500]


def _with_retries(fn, label, attempts=3):
    """Run fn once, retrying on network-level failures (timeout / reset / DNS)."""
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:
            last = exc
            if i < attempts - 1:
                wait = 2 * (i + 1)
                print("RETRY  : " + label + " 网络失败（" + type(exc).__name__ + "），"
                      + str(wait) + " 秒后重试")
                time.sleep(wait)
    print("ERROR  : " + label + " 重试 " + str(attempts) + " 次仍失败：" + repr(last))
    return None


def _blob_sha(data):
    """Git blob SHA-1 — the same value the contents API reports as `sha`."""
    h = hashlib.sha1()
    h.update(b"blob " + str(len(data)).encode("ascii") + b"\0")
    h.update(data)
    return h.hexdigest()


def _put_bytes(path, data, message, token, dry_run=False):
    if dry_run:
        print("DRY-RUN would upload " + path + "  (" + str(len(data)) + " bytes)")
        return True

    def _attempt():
        st, bd = request(API + "/contents/" + path + "?ref=" + BRANCH, token)
        sha = bd.get("sha") if st == 200 and isinstance(bd, dict) else None
        if sha and sha == _blob_sha(data):
            return ("same", 0, None)          # identical content already in the repo
        payload = {"message": message,
                   "content": base64.b64encode(data).decode("ascii"),
                   "branch": BRANCH}
        if sha:
            payload["sha"] = sha
        st2, bd2 = request(API + "/contents/" + path, token, method="PUT", payload=payload)
        return ("put", st2, bd2)

    res = _with_retries(_attempt, path)
    if res is None:
        print("FAILED  " + path + "  （网络中断，未完成；重跑可续）")
        return False
    if res[0] == "same":
        print("SAME    " + path + "  （仓库内容已一致，跳过）")
        return True
    status, body = res[1], res[2]
    ok = status in (200, 201)
    if ok and isinstance(body, dict):
        detail = body.get("commit", {}).get("sha", "")[:8]
        url = body.get("content", {}).get("html_url", "")
    else:
        detail, url = str(body), ""
    print(("UPLOADED " if ok else "FAILED  ") + path + "  http=" + str(status) + "  " + detail)
    if url:
        print("        " + url)
    return ok


def put_file(path, local_path, message, token, dry_run=False):
    with open(local_path, "rb") as fh:
        data = fh.read()
    return _put_bytes(path, data, message, token, dry_run=dry_run)


def put_text(path, text, message, token, dry_run=False):
    """Upload an in-memory text file (landing page, 404 page, README)."""
    return _put_bytes(path, text.encode("utf-8"), message, token, dry_run=dry_run)


def list_months(token):
    """Return the YYYY/MM folders present in the repo, newest first."""
    status, body = request(API + "/git/trees/" + BRANCH + "?recursive=1", token)
    out = set()
    if status == 200 and isinstance(body, dict):
        for node in body.get("tree", []):
            m = re.match(r"^(\d{4})/(\d{2})/calendar\.html$", node.get("path", ""))
            if m:
                out.add(m.group(1) + "/" + m.group(2))
    return sorted(out, reverse=True)


INDEX_CSS = """:root{
  --bg:#0b0c10; --fg:#e9edf5; --muted:#7e8697; --faint:#69707e;
  --wrap:#14161c; --bd:#33363f; --divider:#2b2e37;
  --pill:#1e222b; --pill-fg:#cfd6e2; --link:#7aa2ff;
  --accent:#ffc531; --accent-fg:#1a1c22; --shadow:rgba(0,0,0,.45);
}
[data-theme="light"]{
  --bg:#eef1f7; --fg:#1b1f2a; --muted:#5b6478; --faint:#77809a;
  --wrap:#ffffff; --bd:#d5dbe6; --divider:#e0e5ee;
  --pill:#f7f9fc; --pill-fg:#1b1f2a; --link:#2a52b0;
  --accent:#e0a800; --accent-fg:#1a1c22; --shadow:rgba(20,30,60,.14);
}
*{box-sizing:border-box;margin:0;padding:0}
body{min-height:100vh;background:var(--bg);color:var(--fg);
font-family:"Microsoft YaHei","PingFang SC","Noto Sans CJK SC",system-ui,sans-serif;
display:flex;align-items:center;justify-content:center;padding:32px;
transition:background .18s,color .18s}
.wrap{width:100%;max-width:560px;background:var(--wrap);border:2px solid var(--bd);
border-radius:16px;padding:34px 30px;box-shadow:0 6px 26px var(--shadow);
transition:background .18s,border-color .18s}
h1{font-size:23px;font-weight:800;margin-bottom:8px}
.sub{color:var(--muted);font-size:13.5px;margin-bottom:22px;line-height:1.7}
a.btn{display:block;background:var(--accent);color:var(--accent-fg);font-weight:800;
font-size:16px;text-align:center;padding:14px;border-radius:11px;text-decoration:none;
margin-bottom:18px;transition:filter .15s}
a.btn:hover{filter:brightness(1.08)}
.hint{color:var(--faint);font-size:12.5px;margin-bottom:10px}
ul{list-style:none;display:flex;flex-wrap:wrap;gap:8px}
li a{display:inline-block;background:var(--pill);border:2px solid var(--bd);border-radius:18px;
padding:6px 14px;color:var(--pill-fg);text-decoration:none;font-size:13px;transition:border-color .15s,color .15s}
li a:hover{border-color:var(--link);color:var(--link)}
.foot{margin-top:22px;padding-top:16px;border-top:2px solid var(--divider);
color:var(--faint);font-size:12px;line-height:1.8}
.repo{margin-top:14px;text-align:center}
.repo a{display:inline-flex;align-items:center;gap:7px;background:var(--pill);border:2px solid var(--bd);
border-radius:20px;padding:8px 16px;color:var(--pill-fg);text-decoration:none;font-size:13px;
font-weight:700;transition:border-color .15s,color .15s}
.repo a:hover{border-color:var(--link);color:var(--link)}
.repo svg{flex:0 0 auto}
.theme-toggle{position:fixed;top:18px;right:18px;z-index:9999;display:inline-flex;
align-items:center;gap:8px;background:var(--pill);color:var(--fg);border:2px solid var(--bd);
border-radius:22px;padding:8px 15px;font-family:inherit;font-size:13px;font-weight:700;
line-height:1;cursor:pointer;box-shadow:0 3px 14px var(--shadow);
transition:background .18s,border-color .18s,transform .12s}
.theme-toggle:hover{transform:translateY(-1px);border-color:var(--link)}
.theme-toggle svg{display:block;flex:0 0 auto}
.tt-moon{display:none}
[data-theme="light"] .tt-sun{display:none}
[data-theme="light"] .tt-moon{display:block}
.tt-lbl::after{content:"浅色"}
[data-theme="light"] .tt-lbl::after{content:"深色"}
"""


THEME_JS = "(function(){var K='hsr-theme',s=null;try{s=localStorage.getItem(K)}catch(e){}var m=window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches;document.documentElement.setAttribute('data-theme',s||(m?'light':'dark'));})();"
TOGGLE_JS = "(function(){var K='hsr-theme',r=document.documentElement,btn=document.getElementById('themeBtn');function cur(){return r.getAttribute('data-theme')==='light'?'light':'dark';}if(btn){btn.addEventListener('click',function(){var n=cur()==='light'?'dark':'light';r.setAttribute('data-theme',n);try{localStorage.setItem(K,n)}catch(e){}});}if(window.matchMedia){var mq=window.matchMedia('(prefers-color-scheme: light)');var h=function(e){var s=null;try{s=localStorage.getItem(K)}catch(x){}if(!s){r.setAttribute('data-theme',e.matches?'light':'dark')}};if(mq.addEventListener){mq.addEventListener('change',h)}else if(mq.addListener){mq.addListener(h)}}})();"
THEME_BTN = '<button id="themeBtn" class="theme-toggle" type="button" aria-label="切换浅色 / 深色模式" title="切换浅色 / 深色模式"><svg class="tt-sun" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.4v2.6M12 19v2.6M2.4 12h2.6M19 12h2.6M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M18.7 5.3l-1.8 1.8M7.1 16.9l-1.8 1.8"/></svg><svg class="tt-moon" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.5 14.6A8.6 8.6 0 1 1 9.4 3.5a7 7 0 0 0 11.1 11.1z"/></svg><span class="tt-lbl"></span></button>'


def build_index(months, current):
    """Landing page: jump straight to the current month, else offer the list."""
    opts = "".join('<li><a href="%s/calendar.html">%s</a></li>' % (m, m) for m in months)
    latest = months[0] if months else current
    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>崩坏：星穹铁道 月历</title><style>@@CSS@@</style>
<script>@@THEMEJS@@</script></head>
<body>
@@BTN@@
<div class="wrap">
  <h1>崩坏：星穹铁道 · 月历</h1>
  <div class="sub">每月一份，每周六刷新。红线标的是当前真实时刻，条目可点击跳转官方来源。</div>
  <a class="btn" id="go" href="@@LATEST@@/calendar.html">打开最新月历</a>
  <div class="hint">全部月份</div>
  <ul>@@OPTS@@</ul>
  <div class="foot" id="foot">正在跳转到本月月历…</div>
  <div class="repo">
    <a href="https://github.com/Ayin6667/hsr-calendar" target="_blank" rel="noopener noreferrer">
      <svg viewBox="0 0 16 16" width="15" height="15" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>
      在 GitHub 查看数据与脚本 ↗
    </a>
  </div>
</div>
<script>
(function () {
  var MONTHS = @@JSON@@;
  var LATEST = "@@LATEST@@";
  var go = document.getElementById('go');
  var foot = document.getElementById('foot');
  function ym() {
    var d = new Date(Date.now() + 8 * 3600 * 1000);
    var m = d.getUTCMonth() + 1;
    return d.getUTCFullYear() + '/' + (m < 10 ? '0' + m : '' + m);
  }
  if (MONTHS.indexOf(LATEST) < 0) { MONTHS.unshift(LATEST); }
  var want = ym();
  var target = (MONTHS.indexOf(want) >= 0 ? want : LATEST) + '/calendar.html';
  go.setAttribute('href', target);
  foot.textContent = '目标月份 ' + (MONTHS.indexOf(want) >= 0 ? want : LATEST + '（当月尚未生成）') + '，正在打开…';
  fetch(target, { method: 'HEAD' }).then(function (r) {
    if (r.ok) { location.replace(target); }
    else { foot.textContent = '未能自动打开，请从上方列表选择。'; }
  }).catch(function () { foot.textContent = '未能自动打开，请从上方列表选择。'; });
})();
</script>
<script>@@TOGGLEJS@@</script>
</body></html>
""".replace("@@CSS@@", INDEX_CSS).replace("@@OPTS@@", opts).replace(
        "@@LATEST@@", latest).replace("@@JSON@@", json.dumps(months if months else [latest])).replace(
        "@@THEMEJS@@", THEME_JS).replace("@@TOGGLEJS@@", TOGGLE_JS).replace("@@BTN@@", THEME_BTN)


NOTFOUND_EXTRA_CSS = """
code{background:var(--pill);border:2px solid var(--bd);border-radius:7px;padding:3px 8px;
font-family:ui-monospace,Consolas,"Courier New",monospace;font-size:12.5px;color:var(--link);
word-break:break-all;line-height:1.6}
.codes{margin-top:2px}
.foot a{color:var(--link);text-decoration:none}
.foot a:hover{text-decoration:underline}
"""


def build_404():
    """Standalone 404 page.

    Cloudflare Pages serves the output root's 404.html (with a real 404 status)
    for any unmatched path, so unknown URLs stop masquerading as the homepage.
    """
    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>404 · 页面不存在 · 崩坏：星穹铁道 月历</title>
<meta name="robots" content="noindex">
<style>@@CSS@@@@EXTRA@@</style>
<script>@@THEMEJS@@</script></head>
<body>
@@BTN@@
<div class="wrap">
  <h1>404 · 这一页不在星轨上</h1>
  <div class="sub">这个地址没有对应的页面或月份。可能是该月尚未归档，也可能是链接写错了。</div>
  <a class="btn" href="/">回到首页</a>
  <div class="hint">你请求的路径</div>
  <div class="codes"><code id="miss">/</code></div>
  <div class="foot">
    数据与脚本：<a href="https://github.com/Ayin6667/hsr-calendar">Ayin6667/hsr-calendar</a><br>
    本页由 Cloudflare Pages 的 404.html 返回，HTTP 状态码为 404。
  </div>
</div>
<script>(function(){var e=document.getElementById('miss');
if(e){e.textContent=location.pathname+location.search}})();</script>
<script>@@TOGGLEJS@@</script>
</body></html>
""".replace("@@CSS@@", INDEX_CSS).replace("@@EXTRA@@", NOTFOUND_EXTRA_CSS).replace(
        "@@THEMEJS@@", THEME_JS).replace("@@TOGGLEJS@@", TOGGLE_JS).replace("@@BTN@@", THEME_BTN)


def main():
    argv = sys.argv[1:]
    token_file = None
    dry_run = False
    check_auth = False
    nums = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--dry-run":
            dry_run = True
        elif a == "--check-auth":
            check_auth = True
        elif a == "--token-file":
            i += 1
            token_file = argv[i] if i < len(argv) else None
        elif a.startswith("--token-file="):
            token_file = a.split("=", 1)[1]
        else:
            nums.append(a)
        i += 1

    token, source = resolve_token(token_file)
    if not token:
        return 2
    print("TOKEN  : 已加载（来源：" + source + "）")

    if check_auth:
        status, body = request("https://api.github.com/user", token)
        if status == 200 and isinstance(body, dict):
            print("AUTH   : OK  login=" + str(body.get("login")))
            status2, repo = request(API, token)
            if status2 == 200 and isinstance(repo, dict):
                print("REPO   : OK  " + repo["full_name"] + "  private=" + str(repo["private"])
                      + "  默认分支=" + repo["default_branch"])
                return 0
            print("REPO   : 访问失败 http=" + str(status2) + " " + str(repo))
            return 1
        print("AUTH   : 失败 http=" + str(status) + " " + str(body))
        return 1

    if len(nums) >= 2:
        y, m = int(nums[0]), int(nums[1])
    else:
        print("ERROR: 需要参数 YYYY MM（月历所属年月）")
        return 2
    if not 1 <= m <= 12:
        print("ERROR: 月份超出范围: %d" % m)
        return 2
    month_start = date(y, m, 1)
    month_end = date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)
    prefix = "%04d/%02d" % (y, m)

    files = [
        (prefix + "/calendar.png", os.path.join(HERE, "calendar.png")),
        (prefix + "/calendar.html", os.path.join(HERE, "calendar.html")),
        (prefix + "/events.json", os.path.join(HERE, "events.json")),
    ]
    missing_optional = {prefix + "/calendar.html"}
    msg = "chore(hsr): 月历 %04d-%02d 刷新（%s ~ %s）" % (
        y, m, month_start.isoformat(), month_end.isoformat())
    print("REPO   : " + REPO + "  branch=" + BRANCH)
    print("TARGET : " + prefix + "/   （每月一份，每周覆盖刷新）")
    print("COMMIT : " + msg)
    all_ok = True
    for remote, local in files:
        if not os.path.exists(local):
            if remote in missing_optional:
                print("SKIP    " + remote + "（本地无此文件，非必需）")
                continue
            print("MISSING " + local)
            all_ok = False
            continue
        all_ok = put_file(remote, local, msg, token, dry_run=dry_run) and all_ok

    # 根目录落地页：让站点根路径能直接打开当月月历（任何静态托管都需要）
    months = list_months(token) if not dry_run else []
    if prefix not in months:
        months = sorted(set(months) | {prefix}, reverse=True)
    all_ok = put_text("index.html", build_index(months, prefix),
                      "chore(site): 刷新根目录落地页（可用月份：%s）" % ", ".join(months[:6]),
                      token, dry_run=dry_run) and all_ok

    # 404 页：Cloudflare Pages 对未知路径回退到 index.html 会返回 200，
    # 有了根目录 404.html 才会给出真 404（且不停留在首页内容上）
    all_ok = put_text("404.html", build_404(),
                      "chore(site): 404 页（未知路径返回真 404，不再回退首页）",
                      token, dry_run=dry_run) and all_ok

    # 仓库说明：与站点保持同步（README 内的链接统一指向 ayin.dpdns.org）
    readme = os.path.join(HERE, "README.md")
    if os.path.exists(readme):
        with open(readme, encoding="utf-8") as fh:
            all_ok = put_text("README.md", fh.read(),
                              "docs: 同步 README（月历说明与线上地址）",
                              token, dry_run=dry_run) and all_ok

    print("RESULT : " + ("SUCCESS" if all_ok else "PARTIAL/FAILED"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
