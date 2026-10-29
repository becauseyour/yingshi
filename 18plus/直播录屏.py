# -*- coding: utf-8 -*-
# @name 直播录屏
# @version 1.1.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/直播录屏.py
# @description lookluping 免费直播回放；OmniBox vod_play_sources

import json
import re
from urllib.parse import urlencode
from spider_runner import OmniBox, run

HOST = "https://www.lookluping.xyz"
UA = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
CLASSES = [{"type_id": "free", "type_name": "免费视频"}]

def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default

async def _fetch(path, method="GET", form=None):
    url = path if str(path).startswith("http") else HOST + path
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": HOST + "/",
    }
    opts = {"method": method, "headers": headers, "timeout": 15}
    if form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        opts["body"] = urlencode(form)
        opts["method"] = "POST"
    res = await OmniBox.request(url, opts)
    return res.get("body") or ""

def _wrap_pic(pic):
    if not pic:
        return ""
    pic = pic.strip().replace("&amp;", "&")
    if pic.startswith("//"):
        pic = "https:" + pic
    elif not pic.startswith("http"):
        pic = HOST + (pic if pic.startswith("/") else "/" + pic)
    return pic

def _items(html):
    items, seen = [], set()
    for m in re.finditer(r'<a href="([^"]*?/(\d+)\.html)"([^>]*)>(.*?)</a>', html or "", re.S):
        path, vid = m.group(1).strip(), m.group(2)
        if "/free/" not in path and not path.startswith("free/"):
            continue
        if vid in seen:
            continue
        t = re.search(r'title="([^"]*)"', m.group(3) or "")
        name = (t.group(1).strip() if t else re.sub(r"<[^>]+>", "", m.group(4) or "").strip())
        if not name or len(name) > 120:
            continue
        seen.add(vid)
        after = (html or "")[m.end(): m.end() + 800]
        img = re.search(r'<img[^>]+(?:data-original|original|src)="([^"]+)"', after)
        clean = path.lstrip("/").replace(".html", "")
        if not clean.startswith("free/"):
            clean = "free/" + vid
        items.append({"vod_id": clean, "vod_name": name[:60], "vod_pic": _wrap_pic(img.group(1) if img else ""), "vod_remarks": ""})
    return items

def _pagecount(html, pn=1):
    pages = [int(x) for x in re.findall(r"index_(\d+)\.html", html or "")]
    if pages:
        return max(pages)
    if "下一页" in (html or "") or ("index_%d.html" % (pn + 1)) in (html or ""):
        return pn + 5
    return pn

async def _resolve_m3u8(path, cid, xid):
    r = await _fetch("/e/moyublog/bofang/", method="POST", form={"id": xid, "classid": cid})
    if not r:
        return ""
    try:
        nr = (json.loads(r).get("nr") or "")
    except Exception:
        nr = r
    m = re.search(r'url:\s*["\']([^"\']+)["\']', nr)
    if m:
        return m.group(1).replace("\\/", "/")
    m = re.search(r'src\s*=\s*["\']?\s*\\?(/e/DownSys/play/[^"\']+)', nr)
    u = m.group(1).replace("\\/", "/").replace(" ", "") if m else ""
    if not u:
        u = "/e/DownSys/play/?classid=%s&id=%s&pathid=" % (cid, xid)
    if u.startswith("/"):
        u = HOST + u
    fr = await _fetch(u)
    m = re.search(r'url:\s*["\']([^"\']+)["\']', fr or "")
    if not m:
        m = re.search(r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', fr or "")
    return m.group(1).replace("\\/", "/") if m else ""

async def home(params, context):
    try:
        html = await _fetch("/free/")
        return {"class": CLASSES, "list": _items(html)[:48], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[home] %s" % e)
        return {"class": CLASSES, "list": [], "filters": {}}

async def category(params, context):
    page = _to_int((params or {}).get("page"), 1) or 1
    try:
        url = "/free/" if page <= 1 else "/free/index_%d.html" % page
        html = await _fetch(url)
        if not html or "信息提示" in html[:2000]:
            return {"page": page, "pagecount": 1, "limit": 24, "total": 0, "list": []}
        vod_list = _items(html)
        pagecount = _pagecount(html, page)
        return {"page": page, "pagecount": pagecount, "limit": len(vod_list) or 24, "total": 48 * pagecount, "list": vod_list}
    except Exception as e:
        await OmniBox.log("error", "[category] %s" % e)
        return {"page": 1, "pagecount": 0, "limit": 24, "total": 0, "list": []}

async def detail(params, context):
    vid = str((params or {}).get("videoId") or "").strip()
    if not vid:
        return {"list": []}
    try:
        path = vid.strip("/").replace(".html", "")
        if path.isdigit():
            path = "free/" + path
        html = await _fetch("/" + path + ".html")
        if not html or "buyvideo" not in html:
            return {"list": []}
        m = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
        name = m.group(1).strip() if m else path
        m = re.search(r'<img[^>]+src="([^"]*?/video/[^"]+)"', html) or re.search(r'<img[^>]+src="([^"]+)"', html)
        pic = _wrap_pic(m.group(1) if m else "")
        b = re.search(r'buyvideo" classid="(\d+)" xxid="(\d+)"', html) or re.search(r'classid="(\d+)"[^>]*xxid="(\d+)"', html)
        cid = b.group(1) if b else "26"
        xid = b.group(2) if b else re.search(r"(\d+)", path).group(1)
        play_id = "%s|%s|%s" % (path, cid, xid)
        return {"list": [{
            "vod_id": path,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": name,
            "type_name": "免费视频",
            "vod_play_sources": [{"name": "直播录屏", "episodes": [{"name": "正片", "playId": play_id}]}],
        }]}
    except Exception as e:
        await OmniBox.log("error", "[detail] %s" % e)
        return {"list": []}

async def search(params, context):
    key = str((params or {}).get("keyword") or "").strip()
    if not key:
        return {"list": []}
    raw = key.lower()
    items, seen = [], set()
    try:
        for p in range(1, 6):
            url = "/free/" if p == 1 else "/free/index_%d.html" % p
            html = await _fetch(url)
            if not html or "信息提示" in html[:2000]:
                break
            for it in _items(html):
                if raw not in it["vod_name"].lower() or it["vod_id"] in seen:
                    continue
                seen.add(it["vod_id"])
                items.append(it)
            if len(items) >= 80:
                break
        return {"list": items[:80], "page": 1}
    except Exception as e:
        await OmniBox.log("error", "[search] %s" % e)
        return {"list": []}

async def play(params, context):
    play_id = str((params or {}).get("playId") or (params or {}).get("url") or (params or {}).get("id") or "").strip()
    headers = {"Referer": HOST + "/", "User-Agent": UA}
    if not play_id:
        return {"urls": [], "parse": 0, "header": headers}
    try:
        if play_id.startswith("http") and (".m3u8" in play_id or ".mp4" in play_id):
            return {"urls": [{"name": "播放", "url": play_id}], "parse": 0, "header": headers}
        parts = play_id.split("|")
        if len(parts) >= 3:
            path, cid, xid = parts[0], parts[1], parts[2]
        else:
            path = play_id.strip("/").replace(".html", "")
            if path.isdigit():
                path = "free/" + path
            xid = re.search(r"(\d+)", path).group(1)
            cid = "26"
        m3u8 = await _resolve_m3u8(path, cid, xid)
        if m3u8:
            return {"urls": [{"name": "正片", "url": m3u8}], "parse": 0, "header": headers}
        return {"urls": [], "parse": 0, "header": headers}
    except Exception as e:
        await OmniBox.log("error", "[play] %s" % e)
        return {"urls": [], "parse": 0, "header": headers}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
