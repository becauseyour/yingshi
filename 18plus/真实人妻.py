# -*- coding: utf-8 -*-
# @name 真实人妻
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/真实人妻.py
# @description 真实人妻站点（MacCMS 风格），支持分类/搜索/播放页解析

import re
import json
from urllib.parse import quote, urljoin

from spider_runner import OmniBox, run

HOST = "https://zsrqab03.zsrenqi.xyz"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": HOST + "/",
}

_cache_classes = None


async def _get(url, timeout=15):
    try:
        res = await OmniBox.request(
            url, {"method": "GET", "headers": HEADERS, "timeout": timeout}
        )
        body = res.get("body") or ""
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="ignore")
        status = int(res.get("statusCode") or 0)
        if status and status >= 400:
            return ""
        return str(body)
    except Exception as e:
        await OmniBox.log("error", "[request] %s %s" % (url, e))
        return ""


def _parse_items(html_text):
    items = []
    pattern = r'<li\s+class="content-item">\s*<a[^>]+href="(/index\.php/vod/detail/id/(\d+)\.html)"[^>]*>.*?<img[^>]+data-original="([^"]+)"[^>]*>.*?</a>\s*<div\s+class="title">\s*<h5[^>]*>\s*<a[^>]*>([^<]+)</a>'
    for href, vid, pic, title in re.findall(pattern, html_text, re.S):
        items.append({"vod_id": vid, "vod_name": title.strip(), "vod_pic": pic if pic.startswith("http") else urljoin(HOST, pic), "vod_remarks": ""})
    if items:
        return items
    pattern2 = r'href=["\'](/index\.php/vod/detail/id/(\d+)\.html)["\']'
    for href, vid in re.findall(pattern2, html_text):
        items.append({"vod_id": vid, "vod_name": "video-" + vid, "vod_pic": "", "vod_remarks": ""})
    return items


async def _load_classes():
    global _cache_classes
    if _cache_classes is not None:
        return _cache_classes
    text = await _get(HOST)
    cats = [{"type_id": "home", "type_name": "首页"}]
    if text:
        pattern = r'<a href="(/index\.php/vod/type/id/(\d+)\.html)"[^>]*>([^<]+)</a>'
        seen = {"home"}
        for href, tid, name in re.findall(pattern, text):
            if tid in seen:
                continue
            seen.add(tid)
            cats.append({"type_id": tid, "type_name": name.strip()})
    _cache_classes = cats
    return cats


async def home(params, context):
    classes = await _load_classes()
    text = await _get(HOST)
    list_items = _parse_items(text)[:40] if text else []
    return {"class": classes, "list": list_items, "filters": {}}


async def category(params, context):
    p = params or {}
    tid = str(p.get("categoryId") or p.get("tid") or "").strip()
    page = 1
    try:
        page = max(1, int(p.get("page") or 1))
    except Exception:
        page = 1
    if not tid or tid == "home":
        text = await _get(HOST)
        items = _parse_items(text) if text else []
        return {"list": items, "page": 1, "pagecount": 1, "limit": len(items), "total": len(items)}
    if page == 1:
        url = f"{HOST}/index.php/vod/type/id/{tid}.html"
    else:
        url = f"{HOST}/index.php/vod/type/id/{tid}.html?page={page}"
    html_text = await _get(url)
    items = _parse_items(html_text) if html_text else []
    pagecount = page + 1 if len(items) >= 10 else page
    return {"list": items, "page": page, "pagecount": pagecount, "limit": 20, "total": page * 20}


async def detail(params, context):
    vid = str((params or {}).get("videoId") or (params or {}).get("id") or (params or {}).get("vod_id") or "").strip()
    if not vid:
        return {"list": []}
    url = f"{HOST}/index.php/vod/detail/id/{vid}.html"
    html_text = await _get(url)
    title = vid
    pic = ""
    play_links = []
    if html_text:
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.S)
        if m:
            title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html_text)
        if m:
            pic = m.group(1)
        pattern = r'href=["\'](/index\.php/vod/play/id/\d+/sid/\d+/nid/\d+\.html)["\']'
        for link in set(re.findall(pattern, html_text)):
            play_links.append(urljoin(HOST, link))
    if not play_links:
        play_links.append(f"{HOST}/index.php/vod/play/id/{vid}/sid/1/nid/1.html")
    episodes = []
    for i, pl in enumerate(play_links, 1):
        episodes.append({"name": f"线路{i}", "playId": pl})
    return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": "", "vod_play_sources": [{"name": "播放", "episodes": episodes}]}]}


async def play(params, context):
    play_id = str((params or {}).get("playId") or (params or {}).get("id") or (params or {}).get("url") or "").strip()
    if not play_id:
        return {"parse": 0, "url": ""}
    if play_id.endswith(".html") and play_id.startswith("http"):
        html_text = await _get(play_id)
        if html_text:
            m = re.search(r"(https?://[^\s\"'<>]+?\.(?:m3u8|mp4))", html_text)
            if m:
                return {"parse": 0, "url": m.group(1).replace("\\/", "/"), "header": {"User-Agent": UA, "Referer": HOST + "/"}}
        return {"parse": 1, "url": play_id, "header": {"User-Agent": UA, "Referer": HOST + "/"}}
    return {"parse": 0, "url": play_id, "header": {"User-Agent": UA, "Referer": HOST + "/"}}


async def search(params, context):
    key = str((params or {}).get("wd") or (params or {}).get("key") or "").strip()
    page = 1
    try:
        page = max(1, int((params or {}).get("page") or 1))
    except Exception:
        page = 1
    if not key:
        return {"list": []}
    url = f"{HOST}/index.php/vod/search.html?wd={quote(key)}&page={page}"
    html_text = await _get(url)
    items = _parse_items(html_text) if html_text else []
    return {"list": items}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
