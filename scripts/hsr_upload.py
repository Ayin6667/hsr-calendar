#!/usr/bin/env python3
"""Upload the HSR month calendar + events to the GitHub archive repo.

Usage:
    python hsr_upload.py YYYY MM               # upload/refresh that month
    python hsr_upload.py YYYY MM --dry-run     # resolve paths + token, print, upload nothing
    python hsr_upload.py --check-auth          # verify the token only

One file set per month under YYYY/MM/, overwritten on every weekly run.

Token resolution order (first hit wins):
    1. --token-file <path>
    2. $HSR_GITHUB_TOKEN_FILE
    3. $GITHUB_TOKEN                    (env var still wins over any file)
    4. <script dir>/.hsr_token
    5. %USERPROFILE%\\.dsh\\secrets\\hsr-github-token
Env overrides: GITHUB_REPO (default Ayin6667/hsr-calendar), GITHUB_BRANCH (default main).
"""
import base64
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = os.environ.get("GITHUB_REPO", "Ayin6667/hsr-calendar")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")
API = "https://api.github.com/repos/" + REPO
HERE = os.path.dirname(os.path.abspath(__file__))

TOKEN_TERMS = [
    "ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_", "-----BEGIN",
]


def resolve_token(cli_file=None):
    """Return (token, source_description)."""
    candidates = []
    if cli_file:
        candidates.append((cli_file, "--token-file"))
    if os.environ.get("HSR_GITHUB_TOKEN_FILE"):
        candidates.append((os.environ["HSR_GITHUB_TOKEN_FILE"], "$HSR_GITHUB_TOKEN_FILE"))
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"].strip(), "$GITHUB_TOKEN (环境变量)"
    candidates.append((os.path.join(HERE, ".hsr_token"), "脚本目录 .hsr_token"))
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    candidates.append((os.path.join(home, ".dsh", "secrets", "hsr-github-token"),
                       "%USERPROFILE%\\.dsh\\secrets\\hsr-github-token"))
    problems = []
    for path, label in candidates:
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
    print("ERROR: 未找到可用的 GitHub token。请创建包含 token 的文件，或用 --token-file 指定。")
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:500]


def put_file(path, local_path, message, token, dry_run=False):
    with open(local_path, "rb") as fh:
        content = base64.b64encode(fh.read()).decode("ascii")
    if dry_run:
        print("DRY-RUN would upload " + path + "  (" + str(os.path.getsize(local_path)) + " bytes)")
        return True
    status, body = request(API + "/contents/" + path + "?ref=" + BRANCH, token)
    sha = body.get("sha") if status == 200 and isinstance(body, dict) else None
    payload = {"message": message, "content": content, "branch": BRANCH}
    if sha:
        payload["sha"] = sha
    status, body = request(API + "/contents/" + path, token, method="PUT", payload=payload)
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


def put_text(path, text, message, token, dry_run=False):
    """Upload an in-memory text file (used for the site landing page)."""
    if dry_run:
        print("DRY-RUN would upload " + path + "  (" + str(len(text.encode("utf-8"))) + " bytes)")
        return True
    status, body = request(API + "/contents/" + path + "?ref=" + BRANCH, token)
    sha = body.get("sha") if status == 200 and isinstance(body, dict) else None
    payload = {"message": message,
               "content": base64.b64encode(text.encode("utf-8")).decode(),
               "branch": BRANCH}
    if sha:
        payload["sha"] = sha
    status, body = request(API + "/contents/" + path, token, method="PUT", payload=payload)
    ok = status in (200, 201)
    detail = body.get("commit", {}).get("sha", "")[:8] if ok and isinstance(body, dict) else str(body)
    print(("UPLOADED " if ok else "FAILED  ") + path + "  http=" + str(status) + "  " + detail)
    return ok


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
  <div class="sub">每月一份，每周六刷新。红线标的是当前真实时刻。</div>
  <a class="btn" id="go" href="@@LATEST@@/calendar.html">打开最新月历</a>
  <div class="hint">全部月份</div>
  <ul>@@OPTS@@</ul>
  <div class="foot" id="foot">正在跳转到本月月历…</div>
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

    print("RESULT : " + ("SUCCESS" if all_ok else "PARTIAL/FAILED"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
