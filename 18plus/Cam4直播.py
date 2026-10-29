# -*- coding: utf-8 -*-
# @name Cam4直播
# @version 1.1.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/Cam4直播.py
# @description Cam4 成人直播（仅在线）；OmniBox vod_play_sources

import json
from urllib.parse import quote
from spider_runner import OmniBox, run

HOST = "https://zh.cam4.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
CLASSES = [
    {"type_id": "all", "type_name": "全部"},
    {"type_id": "female", "type_name": "女性"},
    {"type_id": "male", "type_name": "男性"},
    {"type_id": "couples", "type_name": "情侣"},
    {"type_id": "shemale", "type_name": "变性"},
]

def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default

async def _fetch_directory(page=1, tid="all", keyword=""):
    params = "directoryJson=true&online=true&url=true&page=%s" % page
    if tid == "female":
        params += "&gender=female"
    elif tid == "male":
        params += "&gender=male"
    elif tid == "couples":
        params += "&broadcastType=male_female_group"
    elif tid == "shemale":
        params += "&gender=shemale"
    if keyword:
        params += "&showTag=%s" % quote(keyword)
    url = "%s/directoryCams?%s" % (HOST, params)
    headers = {"User-Agent": UA, "Accept": "application/json, text/plain, */*", "Referer": HOST + "/"}
    res = await OmniBox.request(url, {"method": "GET", "headers": headers, "timeout": 12})
    text = (res.get("body") or "").strip()
    if not text:
        return []
    try:
        return (json.loads(text).get("users") or [])
    except Exception:
        return []

def _card(u):
    if not isinstance(u, dict):
        return None
    hls = (u.get("hlsPreviewUrl") or "").strip()
    username = (u.get("username") or "").strip()
    if not username or not hls or ".m3u8" not in hls:
        return None
    title = "%s (%s)" % (username, u.get("countryCode") or "")
    if u.get("age"):
        title += " - %s岁" % u["age"]
    if u.get("resolution"):
        title += " [HD:%s]" % str(u["resolution"]).split(":")[-1]
    return {
        "vod_id": username,
        "vod_name": title,
        "vod_pic": u.get("snapshotImageLink") or "",
        "vod_remarks": str(u.get("statusMessage") or u.get("viewers") or "在线"),
    }

async def _find_user_hls(username):
    name = (username or "").strip().lower()
    if not name:
        return ""
    for page in range(1, 6):
        users = await _fetch_directory(page, "all")
        for u in users:
            if str(u.get("username") or "").lower() == name:
                return (u.get("hlsPreviewUrl") or "").strip()
        if not users:
            break
    users = await _fetch_directory(1, "all", keyword=username)
    for u in users:
        if str(u.get("username") or "").lower() == name:
            return (u.get("hlsPreviewUrl") or "").strip()
        hls = (u.get("hlsPreviewUrl") or "").strip()
        if hls:
            return hls
    return ""

async def home(params, context):
    try:
        users = await _fetch_directory(1, "all")
        videos = [c for c in (_card(u) for u in users) if c]
        return {"class": CLASSES, "list": videos, "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[home] %s" % e)
        return {"class": CLASSES, "list": [], "filters": {}}

async def category(params, context):
    tid = str((params or {}).get("categoryId") or "all")
    page = _to_int((params or {}).get("page"), 1) or 1
    try:
        users = await _fetch_directory(page, tid)
        videos = [c for c in (_card(u) for u in users) if c]
        pagecount = page + 1 if len(videos) >= 20 else page
        return {"list": videos, "page": page, "pagecount": pagecount, "limit": 90, "total": pagecount * 90}
    except Exception as e:
        await OmniBox.log("error", "[category] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "limit": 90, "total": 0}

async def detail(params, context):
    username = str((params or {}).get("videoId") or "").strip()
    if not username:
        return {"list": []}
    try:
        if username.startswith("http") and ".m3u8" in username:
            hls, name = username, "Cam4"
        else:
            hls = await _find_user_hls(username)
            name = username
        if not hls:
            return {"list": [{"vod_id": username, "vod_name": name, "vod_pic": "", "vod_remarks": "暂无流", "vod_play_sources": []}]}
        return {"list": [{
            "vod_id": username,
            "vod_name": name,
            "vod_pic": "",
            "vod_remarks": "直播中",
            "vod_play_sources": [{"name": "Cam4", "episodes": [{"name": "直播源", "playId": hls}]}],
        }]}
    except Exception as e:
        await OmniBox.log("error", "[detail] %s" % e)
        return {"list": []}

async def search(params, context):
    key = str((params or {}).get("keyword") or "").strip()
    page = _to_int((params or {}).get("page"), 1) or 1
    if not key:
        return {"list": []}
    try:
        users = await _fetch_directory(page, "all", keyword=key)
        videos = [c for c in (_card(u) for u in users) if c]
        return {"list": videos, "page": page, "pagecount": page}
    except Exception as e:
        await OmniBox.log("error", "[search] %s" % e)
        return {"list": []}

async def play(params, context):
    play_id = str((params or {}).get("playId") or (params or {}).get("url") or (params or {}).get("id") or "").strip()
    headers = {"User-Agent": UA, "Referer": HOST + "/"}
    if not play_id:
        return {"urls": [], "parse": 0, "header": headers}
    if play_id.startswith("http"):
        return {"urls": [{"name": "直播", "url": play_id}], "parse": 0, "header": headers}
    hls = await _find_user_hls(play_id)
    if hls:
        return {"urls": [{"name": "直播", "url": hls}], "parse": 0, "header": headers}
    return {"urls": [], "parse": 0, "header": headers}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
