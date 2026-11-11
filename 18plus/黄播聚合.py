# -*- coding: utf-8 -*-
# @name 黄播聚合
# @version 1.0.1
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/黄播聚合.py
# @description 国内成人直播聚合（卡哇伊/咪狐/花蝶蝶/蜜桃/77直播等），直连 FLV（wsSecret/wsTime）

import json
from urllib.parse import quote

from spider_runner import OmniBox, run

SITE = "http://api.maiyoux.com:81/mf/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Referer": "http://api.maiyoux.com/",
}

_cache_platforms = None


async def _get(url, timeout=12):
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
        return str(body).strip()
    except Exception as e:
        await OmniBox.log("error", "[request] %s %s" % (url, e))
        return ""


async def _get_json(url):
    text = await _get(url)
    if not text or text[:1] not in ("{", "["):
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


async def _load_platforms():
    global _cache_platforms
    if _cache_platforms is not None:
        return _cache_platforms
    data = await _get_json(SITE + "json.txt")
    platforms = data.get("pingtai") or []
    if not isinstance(platforms, list):
        platforms = []
    result = []
    for p in platforms:
        if not isinstance(p, dict):
            continue
        addr = (p.get("address") or "").strip()
        title = (p.get("title") or "").strip()
        if not addr or not title:
            continue
        result.append({"address": addr, "title": title, "img": p.get("xinimg") or "", "number": str(p.get("Number") or "")})
    _cache_platforms = result
    return result

def _streamer_item(z):
    if not isinstance(z, dict):
        return None
    addr = (z.get("address") or "").strip()
    title = (z.get("title") or "").strip()
    if not addr or not title or not addr.startswith("http"):
        return None
    return {"vod_id": addr, "vod_name": title, "vod_pic": z.get("img") or "", "vod_remarks": "🔴直播"}

async def home(params, context):
    platforms = await _load_platforms()
    classes = [{"type_id": p["address"], "type_name": p["title"]} for p in platforms]
    list_items = []
    if platforms:
        first = platforms[0]
        data = await _get_json(SITE + first["address"])
        for z in (data.get("zhubo") or [])[:40]:
            it = _streamer_item(z)
            if it:
                list_items.append(it)
    return {"class": classes, "list": list_items, "filters": {}}

async def category(params, context):
    p = params or {}
    tid = str(p.get("categoryId") or p.get("tid") or "").strip()
    page = 1
    try:
        page = max(1, int(p.get("page") or 1))
    except Exception:
        page = 1
    if not tid:
        return {"list": [], "page": 1, "pagecount": 0, "limit": 0, "total": 0}
    data = await _get_json(SITE + tid)
    streamers = data.get("zhubo") or []
    items = []
    for z in streamers:
        it = _streamer_item(z)
        if it:
            items.append(it)
    limit = 60
    start = (page - 1) * limit
    page_items = items[start : start + limit]
    total = len(items)
    pagecount = max(1, (total + limit - 1) // limit)
    return {"list": page_items, "page": page, "pagecount": pagecount, "limit": limit, "total": total}

async def detail(params, context):
    vid = str((params or {}).get("videoId") or (params or {}).get("id") or (params or {}).get("vod_id") or "").strip()
    if not vid:
        return {"list": []}
    name = "直播"
    if "?" in vid:
        name = vid.split("?")[0].rsplit("/", 1)[-1]
    return {"list": [{"vod_id": vid, "vod_name": name, "vod_pic": "", "vod_remarks": "🔴直播中", "vod_content": "国内成人直播直链（FLV），地址含时效鉴权，过期需重新进入分类刷新。", "vod_play_sources": [{"name": "直链", "episodes": [{"name": "播放", "playId": vid}]}]}]}

async def play(params, context):
    play_id = str((params or {}).get("playId") or (params or {}).get("id") or (params or {}).get("url") or "").strip()
    if not play_id or not play_id.startswith("http"):
        return {"parse": 0, "url": ""}
    return {"parse": 0, "url": play_id, "header": {"User-Agent": UA, "Referer": "http://api.maiyoux.com/"}}

async def search(params, context):
    key = str((params or {}).get("wd") or (params or {}).get("key") or "").strip().lower()
    if not key:
        return {"list": []}
    platforms = await _load_platforms()
    items = []
    for p in platforms:
        if key in p["title"].lower():
            items.append({"vod_id": p["address"], "vod_name": p["title"], "vod_pic": p["img"], "vod_remarks": "平台"})
    return {"list": items}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
