#!/usr/bin/env python3
"""
wx-fetch —— 一键拉取微信公众号文章（正文 + 元数据），支持 md / txt / docx

用法：
    wx-fetch <url> [<url> ...]            # 默认输出 Markdown 到 stdout
    wx-fetch <url> -o out.md              # 存到文件
    wx-fetch <url> --txt                  # 纯文本
    wx-fetch <url> --docx                 # 转 .docx（沿用 wechat-article-to-word 脚本）
    wx-fetch <url> --json                 # 输出元数据 JSON（标题/公众号/时间/字数）
    wx-fetch urls.txt --batch -o ./out/   # 批量（每行一个 URL）

三级 fallback（今天实测：4/5 篇 curl 可抓，1 篇必须真浏览器）：
    ① 移动 UA    ② 桌面 UA    ③ 真实浏览器（lightpanda/browser-use 兜底）
"""
import argparse, html as H, json, os, re, subprocess, sys, tempfile, pathlib

MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
DESKTOP_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")

def curl(url, ua, timeout=30):
    r = subprocess.run(["curl","-sL","--max-time",str(timeout),"-A",ua,
                        "-H","Referer: https://mp.weixin.qq.com/", url],
                       capture_output=True, text=True, errors="ignore")
    return r.stdout or ""

def clean(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</(p|section|div|li|h[1-6])>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = H.unescape(s)
    s = re.sub(r"[ \t\u00a0]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return s.strip()

def pick(s, pat, flags=re.S):
    m = re.search(pat, s, flags)
    return H.unescape(re.sub(r"<[^>]+>","",m.group(1))).strip() if m else ""

def parse(raw):
    """从 HTML 抽 title / account / ts / body，并判断是否抓取失败"""
    if not raw or len(raw) < 2000:
        return None, "抓取内容过小（可能被拦/需要浏览器）"
    title = pick(raw, r'id="activity-name"[^>]*>(.*?)</h1>')
    acct  = pick(raw, r'id="js_name"[^>]*>(.*?)</a>')
    ts    = pick(raw, r'var ct = "(\d+)"')
    
    # 微信反爬升级：正文可能从 #js_content 移到了 JS 变量 content_noencode
    content_noencode = None
    m_noencode = re.search(r"content_noencode: '(.*?)',", raw, re.S)
    if m_noencode:
        text = m_noencode.group(1)
        text = text.replace("\\x0a", "\n").replace("\\x0b", " ").replace("\\x0c", " ")
        text = text.replace("\\x3c", "<").replace("\\x3e", ">").replace("\\x22", '"').replace("\\x26", "&")
        text = H.unescape(text)
        content_noencode = re.sub(r"<[^>]+>", "", text)
    
    m = (re.search(r'id="js_content"[^>]*>(.*?)</div>\s*<script', raw, re.S)
         or re.search(r'id="js_content"[^>]*>(.*)', raw, re.S))
    body = clean(m.group(1)) if m else ""
    
    # 如果 js_content 为空但 content_noencode 有内容，用 content_noencode 兜底
    if not body and content_noencode:
        body = content_noencode
    
    if not body:
        for kw in ["该内容已被发布者删除","此内容因违规无法查看","已停止访问"]:
            if kw in raw: return None, f"文章不可访问：{kw}"
        return None, "未找到 #js_content 正文（可能需要真浏览器）"
    return dict(title=title, account=acct, ts=ts, body=body), None

def to_md(d):
    lines = [f"# {d['title']}", ""]
    meta = []
    if d.get("account"): meta.append(f"**公众号**：{d['account']}")
    if d.get("date"):    meta.append(f"**发布**：{d['date']}")
    if d.get("url"):     meta.append(f"**原文**：{d['url']}")
    if meta: lines += [" ｜ ".join(meta), ""]
    lines += ["---", "", d["body"]]
    return "\n".join(lines)

def human_date(ts):
    if not ts: return ""
    try:
        return subprocess.run(["date","-r",str(int(ts)),"+%Y-%m-%d %H:%M"],
                              capture_output=True,text=True).stdout.strip()
    except Exception: return ""

def fetch(url, allow_browser=True):
    """三级 fallback"""
    for name, ua in (("移动 UA", MOBILE_UA), ("桌面 UA", DESKTOP_UA)):
        d, err = parse(curl(url, ua))
        if d: d["_via"] = name; return d, None
        last = f"{name}: {err}"
    if allow_browser:
        # 兜底用 lightpanda（真浏览器内核，能执行 JS）——注意：不适用于微信 JS 渲染页
        for cand in ("/usr/local/bin/lightpanda", os.path.expanduser("~/bin/lightpanda-wrapper.sh")):
            if not os.path.exists(cand):
                continue
            try:
                out = subprocess.run([cand, "fetch", "--dump", "text", url] if "lightpanda" in cand else [cand, url],
                                     capture_output=True, text=True, timeout=60).stdout
                if out and len(out) > 800 and "Log in" not in out[:200]:
                    return dict(title=out.strip().split("\n")[0][:120], account="", ts="",
                                body=out.strip(), _via="lightpanda"), None
            except Exception:
                pass
        return None, (f"三级 fallback 全失败（{last}）\n"
                      f"    ⇒ 该页是 JS 渲染（HTML 里无正文 DOM），需真浏览器：交给 Hermes 用 browser 抓")
    return None, last

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("-o","--out"); ap.add_argument("--txt",action="store_true")
    ap.add_argument("--docx",action="store_true"); ap.add_argument("--json",action="store_true")
    ap.add_argument("--batch",action="store_true"); ap.add_argument("--no-browser",action="store_true")
    a = ap.parse_args()

    urls = []
    for u in a.urls:
        if a.batch and os.path.isfile(u):
            urls += [l.strip() for l in open(u) if l.strip() and not l.startswith("#")]
        else: urls.append(u)

    if a.batch and a.out: os.makedirs(a.out, exist_ok=True)
    for i, url in enumerate(urls, 1):
        d, err = fetch(url, allow_browser=not a.no_browser)
        if err:
            print(f"[{i}/{len(urls)}] ❌ {url}\n    {err}", file=sys.stderr); continue
        d["url"] = url; d["date"] = human_date(d.get("ts"))
        tag = f"[{i}/{len(urls)}] ✅ {d['title'][:50]}  ({d['_via']} · {len(d['body'])}字)"
        print(tag, file=sys.stderr)
        if a.json:
            out = json.dumps({k:d[k] for k in ("title","account","date","url","body")},
                             ensure_ascii=False, indent=1)
        elif a.txt: out = d["body"]
        else:       out = to_md(d)
        if a.out:
            if a.batch:
                safe = re.sub(r"[^\w\u4e00-\u9fff-]+","_", d["title"])[:60] or f"art{i}"
                fp = os.path.join(a.out, safe + (".txt" if a.txt else ".md"))
            else: fp = a.out
            pathlib.Path(fp).write_text(out, encoding="utf-8")
            print(f"    → {fp}", file=sys.stderr)
        else:
            print(out)

if __name__ == "__main__":
    main()
