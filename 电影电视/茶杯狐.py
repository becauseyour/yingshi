# -*- coding: utf-8 -*-
# @name 茶杯狐
# @version 1.0.1
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/电影电视/%E8%8C%B6%E6%9D%AF%E7%8B%90.py
# @description 茶杯狐（OmniBox）

import re
from urllib.parse import quote
from spider_runner import OmniBox, run

HOST = "https://citapa.com"
UA = "Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36"

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
]

async def _get(url):
    try:
        res = await OmniBox.request(url, {
            "method": "GET",
            "headers": {"User-Agent": UA, "Referer": HOST + "/", "Origin": HOST},
            "timeout": 15,
        })
        return res.get("body") or ""
    except Exception as e:
        await OmniBox.log("error", f"[茶杯狐] get failed: {e}")
        return ""

def _clean(s):
    return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", s or "")).strip()

def _fix(url):
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return HOST + url
    return url

def _parse_list(html):
    res, seen = [], set()
    for m in re.finditer(r'<div class="module-item">([\s\S]*?)</div>\s*</div>', html or "", re.S):
        item = m.group(1)
        href_m = re.search(r'href=["\']/movie/index(\d+)\.html["\']', item)
        if not href_m:
            continue
        vid = href_m.group(1)
        if vid in seen:
            continue
        seen.add(vid)
        name = ""
        am = re.search(r'alt=["\']([^"\']+)', item)
        if am:
            name = _clean(am.group(1))
        if not name:
            tm = re.search(r'title=["\']([^"\']+)', item)
            name = _clean(tm.group(1)) if tm else ""
        pic = ""
        pm = re.search(r'(?:data-src|data-original|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp|gif)[^"\']*)', item)
        if pm:
            pic = _fix(pm.group(1))
        remarks = ""
        rm = re.search(r'class="module-item-text"[^>]*>(.*?)</div>', item, re.S)
        if rm:
            remarks = _clean(rm.group(1))
        if name:
            res.append({"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": remarks})
    return res

async def home(params, context):
    try:
        html = await _get(HOST + "/")
        return {"class": CLASSES, "list": _parse_list(html), "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] {e}")
        return {"class": CLASSES, "list": [], "filters": {}}

async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("type_id") or "1")
        page = int(p.get("page") or 1)
        url = f"{HOST}/search.php?searchtype=5&tid={tid}&page={page}"
        html = await _get(url)
        items = _parse_list(html)
        return {"list": items, "page": page, "pagecount": page + (1 if len(items) >= 20 else 0), "total": len(items)}
    except Exception as e:
        await OmniBox.log("error", f"[category] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def search(params, context):
    try:
        p = params or {}
        keyword = (p.get("keyword") or "").strip()
        page = int(p.get("page") or 1)
        if not keyword:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        url = f"{HOST}/search.php?searchword={quote(keyword)}&page={page}"
        html = await _get(url)
        return {"list": _parse_list(html), "page": page, "pagecount": 1, "total": 0}
    except Exception as e:
        await OmniBox.log("error", f"[search] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or "").strip()
        if not vid:
            return {"list": []}
        url = f"{HOST}/movie/index{vid}.html"
        html = await _get(url)
        name = ""
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        if m:
            name = _clean(m.group(1))
        if not name:
            m = re.search(r'<meta property="og:title" content="(.*?)"', html)
            name = _clean(m.group(1)) if m else vid
        pic = ""
        m = re.search(r'<meta property="og:image" content="(.*?)"', html)
        if m:
            pic = _fix(m.group(1))
        eps = []
        for m in re.finditer(r'<a[^>]+href=["\']([^"\']*?/play/[^"\']+)["\'][^>]*>(.*?)</a>', html, re.S):
            t = _clean(m.group(2)) or "播放"
            u = _fix(m.group(1))
            if u:
                eps.append({"name": t, "playId": u})
        if not eps:
            eps = [{"name": "播放", "playId": url}]
        return {"list": [{"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_play_sources": [{"name": "茶杯狐", "episodes": eps}]}]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] {e}")
        return {"list": []}

async def play(params, context):
    try:
        p = params or {}
        url = str(p.get("playId") or "").strip()
        headers = {"User-Agent": UA, "Referer": HOST + "/"}
        if not url:
            return {"urls": [], "parse": 0, "header": headers}
        if re.search(r"\.(m3u8|mp4|flv)", url, re.I):
            return {"urls": [{"name": "播放", "url": url}], "parse": 0, "header": headers}
        html = await _get(url)
        m = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
        if m:
            real = m.group(1).replace("\\/", "/")
            return {"urls": [{"name": "播放", "url": real}], "parse": 0, "header": headers}
        return {"urls": [{"name": "播放", "url": url}], "parse": 1, "header": headers}
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
