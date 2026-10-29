# -*- coding: utf-8 -*-
# @name Cam4直播
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/Cam4直播.py
# @description Cam4 成人直播（仅在线房间）；directoryCams JSON + hlsPreviewUrl

"""
Cam4 直播 — OmniBox v1.0.0
站点: https://zh.cam4.com
列表: /directoryCams?directoryJson=true&online=true&url=true
播放: 接口返回的 hlsPreviewUrl（m3u8）
"""

import json
from urllib.parse import quote

from spider_runner import OmniBox, run

HOST = "https://zh.cam4.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

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
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Referer": HOST + "/",
    }
    res = await OmniBox.request(url, {"method": "GET", "headers": headers, "timeout": 12})
    text = (res.get("body") or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except Exception:
        return []
    return data.get("users") or []


def _card(u):
    if not isinstance(u, dict):
        return None
    hls = (u.get("hlsPreviewUrl") or "").strip()
    if not hls or ".m3u8" not in hls:
        return None
    username = u.get("username") or "cam4"
    title = "%s (%s)" % (username, u.get("countryCode") or "")
    if u.get("age"):
        title += " - %s岁" % u["age"]
    if u.get("resolution"):
        res = str(u["resolution"]).split(":")[-1]
        title += " [HD:%s]" % res
    return {
        "vod_id": hls,
        "vod_name": title,
        "vod_pic": u.get("snapshotImageLink") or "",
        "vod_remarks": str(u.get("statusMessage") or u.get("viewers") or "在线"),
    }


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
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 90,
            "total": pagecount * 90,
        }
    except Exception as e:
        await OmniBox.log("error", "[category] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "limit": 90, "total": 0}


async def detail(params, context):
    vid = str((params or {}).get("videoId") or "").strip()
    if not vid:
        return {"list": []}
    # vod_id 直接是 m3u8
    vod = {
        "vod_id": vid,
        "vod_name": "Cam4直播",
        "vod_pic": "",
        "vod_play_from": "Cam4",
        "vod_play_url": "直播源$%s" % vid,
    }
    return {"list": [vod]}


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
    play_url = str(
        (params or {}).get("playUrl")
        or (params or {}).get("url")
        or (params or {}).get("id")
        or ""
    ).strip()
    if "$" in play_url:
        play_url = play_url.split("$", 1)[-1]
    return {
        "parse": 0,
        "url": play_url,
        "header": {"User-Agent": UA, "Referer": HOST + "/"},
    }


if __name__ == "__main__":
    run(
        {
            "home": home,
            "category": category,
            "detail": detail,
            "search": search,
            "play": play,
        }
    )
