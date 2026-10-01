#!/usr/bin/env python3
"""Upload the HSR weekly calendar + events to the GitHub archive repo.

Usage:
    python hsr_upload.py YYYY MM DD            # upload week (DD = week_start Saturday)
    python hsr_upload.py YYYY MM DD --dry-run  # resolve paths + token, print, upload nothing
    python hsr_upload.py --check-auth          # verify the token only

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
import sys
import urllib.error
import urllib.request
from datetime import date

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

    if len(nums) >= 3:
        y, m, d = int(nums[0]), int(nums[1]), int(nums[2])
    else:
        print("ERROR: 需要三个数字参数 YYYY MM DD（week_start，周六）")
        return 2
    ws = date(y, m, d)
    if ws.weekday() != 5:
        print("WARN   : %s 不是周六，按给定日期计算 ISO 周" % ws.isoformat())
    iso = ws.isocalendar()
    week_tag = "W%02d" % iso[1]
    prefix = "%04d/%s" % (iso[0], week_tag)

    files = [
        (prefix + "/calendar.png", os.path.join(HERE, "calendar.png")),
        (prefix + "/calendar.html", os.path.join(HERE, "calendar.html")),
        (prefix + "/events.json", os.path.join(HERE, "events.json")),
    ]
    missing_optional = {prefix + "/calendar.html"}
    msg = "chore(hsr): 周历 %s 归档（week_start %s, ISO %s/%s）" % (
        week_tag, ws.isoformat(), iso[0], week_tag)
    print("REPO   : " + REPO + "  branch=" + BRANCH)
    print("TARGET : " + prefix + "/")
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
    print("RESULT : " + ("SUCCESS" if all_ok else "PARTIAL/FAILED"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
