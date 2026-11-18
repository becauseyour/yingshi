# -*- coding: utf-8 -*-
# @name 猫又影视
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/电影电视/猫又影视.py
# @description 猫又影视（OmniBox）多域名

import re
import json
from urllib.parse import quote
from spider_runner import OmniBox, run

HOSTS = [
    "https://www.maoyou.me",
    "https://maoyou.top",
    "https://www.imaoyou.cc",
    "https://www.maoyou.mobi",
    "https://www.imaoyou.net",
]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "5", "type_name": "短剧"},
]

_host = HOSTS[0]

async def _get(url):
    global _host
    for h in [_host] + [x for x in HOSTS if x != _host]:
        try:
            u = url.replace(_host, h) if url.startswith(_host) else (h + url if url.startswith("/") else url)
            res = await OmniBox.request(u, {"method": "GET", "headers": {"User-Agent": UA, "Referer": h + "/"}, "timeout": 12})
            body = res.get("body") or ""
            if body and len(body) > 500 and ("maoyou" in body.lower() or "vodshow" in body or "myui" in body):
                _host = h
                return body
        except Exception:
            continue
    return ""

def _cards(html):
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="(/maoyou/\d+\.html)"[^>]*(?:title="([^"]*)")?', html or ""):
        href = m.group(1)
        vid = re.search(r"/maoyou/(\d+)", href)
        if not vid:
            continue
        vid = vid.group(1)
        if vid in seen:
            continue
        seen.add(vid)
        title = m.group(2) or ""
        if not title:
            tm = re.search(r'title="([^"]*)"', html[m.start():m.start()+300])
            title = tm.group(1) if tm else vid
        im = re.search(r'(?:data-original|data-src|src)="([^"]+\.(?:jpg|jpeg|png|webp))"', html[max(0,m.start()-200):m.end()+200])
        pic = im.group(1) if im else ""
        if pic and not pic.startswith("http"):
            pic = _host + pic if pic.startswith("/") else pic
        out.append({"vod_id": vid, "vod_name": title.strip(), "vod_pic": pic, "vod_remarks": ""})
    return out

async def home(params, context):
    try:
        html = await _get(_host + "/")
        return {"class": CLASSES, "list": _cards(html)[:40], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] {e}")
        return {"class": CLASSES, "list": [], "filters": {}}

async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("type_id") or "1")
        page = int(p.get("page") or 1)
        parts = [tid] + [""] * 11
        if page > 1:
            parts[8] = str(page)
        url = f"{_host}/vodshow/{'-'.join(parts)}.html"
        html = await _get(url)
        items = _cards(html)
        return {"list": items, "page": page, "pagecount": page + (1 if len(items) >= 20 else 0), "total": len(items)}
    except Exception as e:
        await OmniBox.log("error", f"[category] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def search(params, context):
    try:
        p = params or {}
        key = (p.get("keyword") or "").strip()
        page = int(p.get("page") or 1)
        if len(key) < 2:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        parts = [quote(key)] + [""] * 13
        if page > 1:
            parts[10] = str(page)
        url = f"{_host}/vodsearch/{'-'.join(parts)}.html"
        html = await _get(url)
        return {"list": _cards(html), "page": page, "pagecount": 1, "total": 0}
    except Exception as e:
        await OmniBox.log("error", f"[search] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or "").strip()
        if not vid:
            return {"list": []}
        url = f"{_host}/maoyou/{vid}.html"
        html = await _get(url)
        title = re.search(r"<h1[^>]*>(.*?)</h1>", html or "")
        title = re.sub(r"<[^>]+>", "", title.group(1)).strip() if title else vid
        pic = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html or "")
        pic = pic.group(1) if pic else ""
        eps = []
        for a in re.finditer(r'href="(/tv/%s-(\d+)-(\d+)\.html)"[^>]*>([^<]*)<' % re.escape(vid), html or ""):
            href, name = a.group(1), a.group(4).strip() or "播放"
            eps.append({"name": name, "playId": href})
        if not eps:
            eps = [{"name": "播放", "playId": f"/tv/{vid}-1-1.html"}]
        return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_play_sources": [{"name": "猫又", "episodes": eps[:100]}]}]}
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
        url = _host + pid if pid.startswith("/") else pid
        html = await _get(url)
        m = re.search(r"player_aaaa\s*=\s*(\{.*?\})\s*</script>", html or "", re.S)
        if m:
            data = json.loads(m.group(1))
            u = data.get("url", "").replace("\\/", "/")
            enc = str(data.get("encrypt", "0"))
            if enc == "1":
                from urllib.parse import unquote
                u = unquote(u)
            elif enc == "2":
                import base64
                from urllib.parse import unquote
                u = unquote(base64.b64decode(u).decode("utf-8", "ignore"))
            if u and re.search(r"\.(m3u8|mp4)", u, re.I):
                return {"urls": [{"name": "播放", "url": u}], "parse": 0, "header": {"User-Agent": UA}}
            if u:
                return {"urls": [{"name": "播放", "url": u}], "parse": 1, "header": headers}
        return {"urls": [{"name": "播放", "url": pid}], "parse": 1, "header": headers}
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
