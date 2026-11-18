# -*- coding: utf-8 -*-
# @name 韩国色情电影
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/韩国色情电影.py
# @description 韩国色情电影（OmniBox）

import re
from urllib.parse import quote
from spider_runner import OmniBox, run

HOST = "https://koreanpornmovie.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

CLASSES = [
    {"type_id": "latest", "type_name": "最新"},
    {"type_id": "longest", "type_name": "最长"},
    {"type_id": "random", "type_name": "随机"},
]

async def _get(url):
    try:
        res = await OmniBox.request(url, {"method": "GET", "headers": {"User-Agent": UA, "Referer": HOST + "/"}, "timeout": 15})
        return res.get("body") or ""
    except Exception:
        return ""

def _cards(html):
    out, seen = [], set()
    for m in re.finditer(r'<article[^>]*class="[^"]*thumb-block[^"]*"[^>]*>(.*?)</article>', html or "", re.S | re.I):
        block = m.group(1)
        hm = re.search(r'<a[^>]+href=["\']([^"\']+)["\']', block)
        if not hm:
            continue
        href = hm.group(1)
        vid = href.rstrip("/").split("/")[-1]
        if not vid or vid in seen:
            continue
        seen.add(vid)
        im = re.search(r'<img[^>]+(?:class="video-main-thumb")?[^>]+src=["\']([^"\']+)["\']', block)
        pic = im.group(1) if im else ""
        tm = re.search(r'<header[^>]*class="entry-header"[^>]*>.*?<span[^>]*>(.*?)</span>', block, re.S)
        title = re.sub(r"<[^>]+>", "", tm.group(1)).strip() if tm else vid
        dm = re.search(r'<span[^>]*class="duration"[^>]*>(.*?)</span>', block)
        rem = re.sub(r"<[^>]+>", "", dm.group(1)).strip() if dm else ""
        out.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": rem})
    return out

async def home(params, context):
    try:
        html = await _get(HOST + "/")
        return {"class": CLASSES, "list": _cards(html)[:30], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] {e}")
        return {"class": CLASSES, "list": [], "filters": {}}

async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("type_id") or "latest")
        page = int(p.get("page") or 1)
        url = HOST + "/"
        if tid == "longest":
            url += "?filter=longest"
        elif tid == "random":
            url += "?filter=random"
        if page > 1:
            url = url.rstrip("/") + f"/page/{page}/"
        html = await _get(url)
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
        url = f"{HOST}/?s={quote(key)}"
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
        url = f"{HOST}/{vid}"
        html = await _get(url)
        title = re.search(r'<h1[^>]*class="entry-title"[^>]*>(.*?)</h1>', html or "")
        title = re.sub(r"<[^>]+>", "", title.group(1)).strip() if title else vid
        pic = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html or "")
        pic = pic.group(1) if pic else ""
        # 播放地址
        play = ""
        mm = re.search(r'<meta[^>]+itemprop=["\']contentURL["\'][^>]+content=["\']([^"\']+)["\']', html or "")
        if mm:
            play = mm.group(1)
        if not play:
            mm = re.search(r'(https?://[^\s"\']+\.mp4[^\s"\']*)', html or "")
            play = mm.group(1) if mm else ""
        eps = [{"name": "播放", "playId": play or vid}]
        return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_play_sources": [{"name": "韩国", "episodes": eps}]}]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] {e}")
        return {"list": []}

async def play(params, context):
    try:
        p = params or {}
        pid = str(p.get("playId") or "").strip()
        headers = {"User-Agent": UA, "Referer": HOST + "/"}
        if pid.startswith("http") and re.search(r"\.(mp4|m3u8)", pid, re.I):
            return {"urls": [{"name": "播放", "url": pid}], "parse": 0, "header": headers}
        return {"urls": [{"name": "播放", "url": pid}], "parse": 1, "header": headers}
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
