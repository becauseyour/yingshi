# -*- coding: utf-8 -*-
# @name 网飞TV
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/电影电视/网飞TV.py
# @description 网飞TV/冰峰剧场（OmniBox）

import re
import json
from urllib.parse import quote, urljoin
from spider_runner import OmniBox, run

HOST = "https://www.bfjc.cc"
UA = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/131.0.0.0 Mobile Safari/537.36"

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "电视剧"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "5", "type_name": "纪录片"},
    {"type_id": "47", "type_name": "短剧"},
]

async def _get(url):
    try:
        if not url.startswith("http"):
            url = urljoin(HOST + "/", url)
        res = await OmniBox.request(url, {"method": "GET", "headers": {"User-Agent": UA, "Referer": HOST + "/", "Cookie": "age_edge=1"}, "timeout": 15})
        return res.get("body") or ""
    except Exception as e:
        await OmniBox.log("error", f"[网飞] get failed: {e}")
        return ""

def _clean(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()

def _parse_list(html):
    items, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="([^"]*/voddetail/[^"]+\.html)"[^>]*>', html or ""):
        href = m.group(1)
        vid = re.search(r'/voddetail/([^/.]+)', href)
        vid = vid.group(1) if vid else href
        if vid in seen:
            continue
        seen.add(vid)
        snippet = html[m.start():m.start()+1200]
        title = ""
        tm = re.search(r'(?:title|alt)="([^"]+)"', snippet)
        if tm:
            title = _clean(tm.group(1))
        pic = ""
        pm = re.search(r'(?:data-original|data-src|src)="([^"]+)"', snippet)
        if pm:
            pic = pm.group(1)
            if pic.startswith("//"):
                pic = "https:" + pic
            elif pic.startswith("/"):
                pic = HOST + pic
        if title and title.lower() not in {"play", "detail", "more"}:
            items.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": ""})
    return items

async def home(params, context):
    try:
        html = await _get(HOST + "/")
        return {"class": CLASSES, "list": _parse_list(html)[:40], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] {e}")
        return {"class": CLASSES, "list": [], "filters": {}}

async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("type_id") or "1")
        page = int(p.get("page") or 1)
        if page == 1:
            url = f"{HOST}/vodshow/id/{tid}.html"
        else:
            url = f"{HOST}/vodshow/page/{page}/id/{tid}.html"
        html = await _get(url)
        items = _parse_list(html)
        return {"list": items, "page": page, "pagecount": page + (1 if items else 0), "total": len(items)}
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
        url = f"{HOST}/vod/search?wd={quote(keyword)}"
        if page > 1:
            url += f"&page={page}"
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
        if vid.isdigit():
            vid = f"/voddetail/{vid}.html"
        url = urljoin(HOST + "/", vid)
        html = await _get(url)
        title = ""
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html or "", re.S)
        if m:
            title = _clean(m.group(1))
        pic = ""
        m = re.search(r'og:image"[^>]*content="([^"]+)"', html or "")
        if m:
            pic = m.group(1)
        eps = []
        for em in re.finditer(r'<a[^>]+href="([^"]*/(?:vodplay|play)/[^"]+)"[^>]*>(.*?)</a>', html or "", re.S):
            href = em.group(1)
            name = _clean(em.group(2)) or "播放"
            if name and len(name) < 30:
                full = urljoin(HOST + "/", href)
                eps.append({"name": name, "playId": full})
        if not eps:
            eps = [{"name": "播放", "playId": url}]
        return {"list": [{"vod_id": vid, "vod_name": title or vid, "vod_pic": pic, "vod_play_sources": [{"name": "网飞TV", "episodes": eps[:100]}]}]}
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
        if re.search(r"\.(m3u8|mp4)", url, re.I):
            return {"urls": [{"name": "播放", "url": url}], "parse": 0, "header": headers}
        html = await _get(url)
        m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', html or "", re.S)
        if m:
            try:
                pd = json.loads(m.group(1))
                real = pd.get("url") or ""
                if real:
                    return {"urls": [{"name": "播放", "url": real}], "parse": 0, "header": headers}
            except Exception:
                pass
        m = re.search(r'(https?://[^"\']+\.m3u8[^"\']*)', html or "")
        if m:
            return {"urls": [{"name": "播放", "url": m.group(1)}], "parse": 0, "header": headers}
        return {"urls": [{"name": "播放", "url": url}], "parse": 1, "header": headers}
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
