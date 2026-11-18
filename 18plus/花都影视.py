# -*- coding: utf-8 -*-
# @name 花都影视
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/花都影视.py
# @description 花都影视（OmniBox）多域名

import re
import base64
from urllib.parse import quote, unquote
from spider_runner import OmniBox, run

HOSTS = [
    "https://hd28.huadutx.com",
    "https://rb.huaduys.org",
    "https://abc.hdfby.com",
    "https://b.hdfby.com",
    "https://b.hdfby.net",
    "https://b.hdfby.org",
]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36"

FALLBACK_CATS = [
    {"type_id": "/vodshow/1-----------.html", "type_name": "中文字幕"},
    {"type_id": "/vodshow/2-----------.html", "type_name": "无字幕"},
    {"type_id": "/vodshow/3-----------.html", "type_name": "国产"},
    {"type_id": "/vodshow/4-----------.html", "type_name": "动漫"},
    {"type_id": "/vodshow/5-----------.html", "type_name": "欧美"},
    {"type_id": "/vodshow/6-----------.html", "type_name": "中字无码"},
    {"type_id": "/vodshow/10-----------.html", "type_name": "国产精品"},
    {"type_id": "/vodshow/11-----------.html", "type_name": "国产传媒"},
]

_host = HOSTS[0]

async def _get(url):
    global _host
    for h in [_host] + [x for x in HOSTS if x != _host]:
        try:
            u = url if url.startswith("http") else (h + url if url.startswith("/") else url)
            if url.startswith(_host):
                u = url.replace(_host, h, 1)
            res = await OmniBox.request(u, {"method": "GET", "headers": {"User-Agent": UA, "Referer": h + "/"}, "timeout": 12})
            body = res.get("body") or ""
            if isinstance(body, bytes):
                for enc in ("utf-8", "gbk", "gb2312"):
                    try:
                        body = body.decode(enc)
                        break
                    except Exception:
                        body = body.decode("utf-8", "ignore")
            if body and len(body) > 300 and ("花都" in body or "voddetail" in body or "stui" in body):
                _host = h
                return body
        except Exception:
            continue
    return ""

def _cards(html):
    out, seen = [], set()
    for m in re.finditer(r'<li[\s\S]*?</li>', html or ""):
        b = m.group(0)
        if "voddetail" not in b:
            continue
        if any(x in b for x in ["广告", "棋牌", "赌场", "博彩"]):
            continue
        hm = re.search(r'href=["\']([^"\']*voddetail[^"\']+)["\']', b)
        if not hm:
            continue
        href = hm.group(1)
        if href in seen:
            continue
        seen.add(href)
        tm = re.search(r'title=["\']([^"\']+)["\']', b)
        name = tm.group(1).strip() if tm else ""
        if not name:
            nm = re.search(r'<h4[^>]*>[\s\S]*?<a[^>]*>([\s\S]*?)</a>', b)
            name = re.sub(r"<[^>]+>", "", nm.group(1)).strip() if nm else ""
        if len(name) < 2:
            continue
        im = re.search(r'(?:data-original|data-src|src)=["\']([^"\']+)["\']', b)
        pic = im.group(1) if im else ""
        if pic and not pic.startswith("http"):
            pic = _host + pic if pic.startswith("/") else pic
        out.append({"vod_id": href, "vod_name": name, "vod_pic": pic, "vod_remarks": ""})
    return out

async def home(params, context):
    try:
        html = await _get(_host + "/")
        cats = []
        for href, name in re.findall(r'<a[^>]+href=["\']([^"\']*(?:vodtype|vodshow)[^"\']+)["\'][^>]*>([\s\S]*?)</a>', html or ""):
            name = re.sub(r"<[^>]+>", "", name).strip()
            if not name or name in ["首页", "发布页"]:
                continue
            cid = href.replace("vodtype", "vodshow")
            if "-----------" not in cid:
                cid = cid.split(".html")[0] + "-----------.html" if ".html" in cid else cid
            cats.append({"type_id": cid, "type_name": name})
        if len(cats) < 3:
            cats = FALLBACK_CATS
        return {"class": cats[:16], "list": _cards(html)[:30], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] {e}")
        return {"class": FALLBACK_CATS, "list": [], "filters": {}}

async def category(params, context):
    try:
        p = params or {}
        cid = str(p.get("categoryId") or p.get("type_id") or "/vodshow/1-----------.html")
        page = int(p.get("page") or 1)
        base = cid.split("---.html")[0] if "---.html" in cid else cid.replace(".html", "")
        url = f"{base}{page}---.html" if page > 1 else cid
        html = await _get(url if url.startswith("http") else _host + url)
        items = _cards(html)
        return {"list": items, "page": page, "pagecount": page + (1 if len(items) >= 15 else 0), "total": len(items)}
    except Exception as e:
        await OmniBox.log("error", f"[category] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def search(params, context):
    try:
        p = params or {}
        key = (p.get("keyword") or "").strip()
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        url = f"{_host}/vodsearch/-------------.html?wd={quote(key)}"
        html = await _get(url)
        return {"list": _cards(html), "page": 1, "pagecount": 1, "total": 0}
    except Exception as e:
        await OmniBox.log("error", f"[search] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or "").strip()
        if not vid:
            return {"list": []}
        url = vid if vid.startswith("http") else _host + vid
        html = await _get(url)
        title = re.search(r"<h1[^>]*>(.*?)</h1>", html or "")
        title = re.sub(r"<[^>]+>", "", title.group(1)).strip() if title else vid.split("/")[-1]
        pm = re.search(r'class=["\']btn btn-primary["\'][^>]+href=["\']([^"\']+)["\']', html or "")
        play = pm.group(1) if pm else vid
        if play and not play.startswith("http"):
            play = _host + play
        eps = [{"name": "播放", "playId": play}]
        return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": "", "vod_play_sources": [{"name": "花都", "episodes": eps}]}]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] {e}")
        return {"list": []}

async def play(params, context):
    try:
        p = params or {}
        pid = str(p.get("playId") or "").strip()
        headers = {"User-Agent": UA, "Referer": _host + "/"}
        if pid.startswith("http") and re.search(r"\.(m3u8|mp4)", pid, re.I):
            return {"urls": [{"name": "播放", "url": pid}], "parse": 0, "header": headers}
        html = await _get(pid)
        u = ""
        for pat in [r'"","url":"([^"]+)"', r'"url":"([^"]+)"']:
            m = re.search(pat, html or "")
            if m:
                u = m.group(1)
                break
        if u:
            try:
                u = unquote(base64.b64decode(u).decode("utf-8"))
            except Exception:
                u = unquote(u)
            u = u.replace("\\/", "/")
            if u:
                return {"urls": [{"name": "播放", "url": u}], "parse": 0 if re.search(r"\.(m3u8|mp4)", u, re.I) else 1, "header": headers}
        return {"urls": [{"name": "播放", "url": pid}], "parse": 1, "header": headers}
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
