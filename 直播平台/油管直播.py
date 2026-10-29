# -*- coding: utf-8 -*-
# @name 油管直播
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%9B%B4%E6%92%AD%E5%B9%B3%E5%8F%B0/油管直播.py
# @description YouTube 直播搜索；解析 hlsManifestUrl 直链播放（无本地代理）

"""
油管直播 — OmniBox v1.0.0
列表: YouTube 搜索 (sp=直播过滤)
播放: 页面 ytInitialPlayerResponse / player API 取 hlsManifestUrl
说明: 部分地区/网络可能需代理；无 OmniBox localProxy 时直接返回 m3u8
"""

import json
import re
from urllib.parse import quote

from spider_runner import OmniBox, run

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.youtube.com/",
}

LIVE_CLASSES = [
    {"type_id": "live", "type_name": "正在直播"},
    {"type_id": "news live", "type_name": "新闻直播"},
    {"type_id": "music live", "type_name": "音乐直播"},
    {"type_id": "lofi live", "type_name": "Lofi直播"},
    {"type_id": "space live", "type_name": "太空直播"},
    {"type_id": "nature live", "type_name": "自然直播"},
    {"type_id": "game live", "type_name": "游戏直播"},
    {"type_id": "sports live", "type_name": "体育直播"},
]


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _extract_json_after(text, marker):
    pos = (text or "").find(marker)
    if pos < 0:
        return None
    start = text.find("{", pos)
    if start < 0:
        return None
    depth = 0
    in_str = None
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if in_str:
            if char == in_str:
                in_str = None
            continue
        if char in ('"', "'"):
            in_str = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : index + 1])
                except Exception:
                    return None
    return None


def _parse_renderer(renderer):
    try:
        video_id = renderer.get("videoId")
        if not video_id:
            nav = renderer.get("navigationEndpoint") or {}
            video_id = (nav.get("watchEndpoint") or {}).get("videoId")
        if not video_id:
            return None
        title_obj = renderer.get("title") or renderer.get("headline") or {}
        title = title_obj.get("simpleText") or "".join(
            [x.get("text", "") for x in title_obj.get("runs", [])]
        ) or "YouTube Live"
        badges = json.dumps(renderer.get("badges") or [], ensure_ascii=False)
        overlays = json.dumps(renderer.get("thumbnailOverlays") or [], ensure_ascii=False)
        view = ""
        vt = renderer.get("viewCountText") or {}
        view = vt.get("simpleText") or "".join([x.get("text", "") for x in vt.get("runs", [])])
        meta = (" ".join([badges, overlays, view])).lower()
        is_live = "live" in meta or "直播" in meta or "watching" in view.lower()
        return {
            "vod_id": video_id,
            "vod_name": title,
            "vod_pic": "https://img.youtube.com/vi/%s/hqdefault.jpg" % video_id,
            "vod_remarks": "直播" if is_live else (view or "Live"),
        }
    except Exception:
        return None


def _extract_videos(data, limit=30):
    videos = []
    seen = set()

    def scan(obj):
        if len(videos) >= limit:
            return
        if isinstance(obj, dict):
            for key in ("videoRenderer", "compactVideoRenderer", "gridVideoRenderer"):
                if key in obj:
                    item = _parse_renderer(obj[key])
                    if item and item["vod_id"] not in seen:
                        seen.add(item["vod_id"])
                        videos.append(item)
            for value in obj.values():
                scan(value)
        elif isinstance(obj, list):
            for value in obj:
                scan(value)

    scan(data)
    return videos[:limit]


async def _search_page(keyword):
    # sp=EgJAAQ%3D%3D 过滤直播
    url = (
        "https://www.youtube.com/results?search_query=%s&sp=EgJAAQ%%253D%%253D"
        % quote(str(keyword or "live"))
    )
    res = await OmniBox.request(url, {"method": "GET", "headers": HEADERS, "timeout": 15})
    html = res.get("body") or ""
    data = _extract_json_after(html, "ytInitialData") or {}
    return _extract_videos(data, 30)


async def _extract_hls(video_id):
    watch = "https://www.youtube.com/watch?v=%s" % video_id
    res = await OmniBox.request(watch, {"method": "GET", "headers": HEADERS, "timeout": 15})
    page = res.get("body") or ""
    player = _extract_json_after(page, "ytInitialPlayerResponse") or {}
    streaming = player.get("streamingData") or {}
    hls = (streaming.get("hlsManifestUrl") or "").strip()
    details = player.get("videoDetails") or {}
    title = details.get("title") or video_id
    status = ((player.get("playabilityStatus") or {}).get("status") or "")
    reason = ((player.get("playabilityStatus") or {}).get("reason") or "")

    if not hls:
        # 尝试 ANDROID player API
        m = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', page)
        api_key = m.group(1) if m else ""
        if api_key:
            clients = [
                {
                    "clientName": "ANDROID",
                    "clientVersion": "21.02.35",
                    "androidSdkVersion": 30,
                    "userAgent": "com.google.android.youtube/21.02.35 (Linux; U; Android 11) gzip",
                    "hl": "en",
                    "gl": "US",
                },
                {
                    "clientName": "IOS",
                    "clientVersion": "21.02.3",
                    "deviceMake": "Apple",
                    "deviceModel": "iPhone16,2",
                    "userAgent": "com.google.ios.youtube/21.02.3 (iPhone16,2; U; CPU iOS 18_3_2 like Mac OS X;)",
                    "hl": "en",
                    "gl": "US",
                },
            ]
            for client in clients:
                try:
                    payload = {
                        "context": {"client": client},
                        "videoId": video_id,
                        "contentCheckOk": True,
                        "racyCheckOk": True,
                    }
                    api_url = (
                        "https://www.youtube.com/youtubei/v1/player?key=%s&prettyPrint=false"
                        % quote(api_key)
                    )
                    headers = dict(HEADERS)
                    headers.update(
                        {
                            "Content-Type": "application/json",
                            "Origin": "https://www.youtube.com",
                            "User-Agent": client.get("userAgent") or UA,
                        }
                    )
                    r2 = await OmniBox.request(
                        api_url,
                        {
                            "method": "POST",
                            "headers": headers,
                            "body": json.dumps(payload),
                            "timeout": 12,
                        },
                    )
                    data = json.loads((r2.get("body") or "{}"))
                    st = data.get("streamingData") or {}
                    if st.get("hlsManifestUrl"):
                        hls = st["hlsManifestUrl"]
                        details = data.get("videoDetails") or details
                        title = details.get("title") or title
                        break
                except Exception:
                    continue
    return {
        "id": video_id,
        "title": title,
        "hls_url": hls,
        "status": status,
        "reason": reason,
        "is_live": bool(details.get("isLiveContent") or hls),
    }


async def home(params, context):
    try:
        videos = await _search_page("live")
        return {"class": LIVE_CLASSES, "list": videos, "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[home] %s" % e)
        return {"class": LIVE_CLASSES, "list": [], "filters": {}}


async def category(params, context):
    tid = str((params or {}).get("categoryId") or "live")
    page = _to_int((params or {}).get("page"), 1) or 1
    try:
        keyword = tid if tid else "live"
        if "live" not in keyword.lower() and "直播" not in keyword:
            keyword = keyword + " live"
        videos = await _search_page(keyword)
        return {
            "list": videos,
            "page": page,
            "pagecount": page,
            "limit": len(videos),
            "total": len(videos),
        }
    except Exception as e:
        await OmniBox.log("error", "[category] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "limit": 20, "total": 0}


async def detail(params, context):
    video_id = str((params or {}).get("videoId") or "").strip()
    if not video_id:
        return {"list": []}
    # 支持完整 URL
    m = re.search(r"(?:v=|/v/|youtu\.be/)([0-9A-Za-z_-]{11})", video_id)
    if m:
        video_id = m.group(1)
    try:
        data = await _extract_hls(video_id)
        title = data.get("title") or video_id
        if data.get("hls_url"):
            status = "直播中"
        elif data.get("status") == "LIVE_STREAM_OFFLINE":
            status = data.get("reason") or "未开播"
        else:
            status = data.get("reason") or data.get("status") or "无HLS"
        vod = {
            "vod_id": video_id,
            "vod_name": title,
            "vod_pic": "https://img.youtube.com/vi/%s/hqdefault.jpg" % video_id,
            "vod_remarks": status,
            "vod_play_from": "直播",
            "vod_play_url": "播放$%s" % video_id,
        }
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", "[detail] %s" % e)
        return {
            "list": [
                {
                    "vod_id": video_id,
                    "vod_name": video_id,
                    "vod_pic": "https://img.youtube.com/vi/%s/hqdefault.jpg" % video_id,
                    "vod_play_from": "直播",
                    "vod_play_url": "播放$%s" % video_id,
                }
            ]
        }


async def search(params, context):
    key = str((params or {}).get("keyword") or "").strip()
    if not key:
        return {"list": []}
    if "live" not in key.lower() and "直播" not in key:
        key = key + " live"
    try:
        videos = await _search_page(key)
        return {"list": videos, "page": 1, "pagecount": 1}
    except Exception as e:
        await OmniBox.log("error", "[search] %s" % e)
        return {"list": []}


async def play(params, context):
    raw = str(
        (params or {}).get("playUrl")
        or (params or {}).get("url")
        or (params or {}).get("id")
        or ""
    ).strip()
    if "$" in raw:
        raw = raw.split("$", 1)[-1]
    video_id = raw
    m = re.search(r"(?:v=|/v/|youtu\.be/)([0-9A-Za-z_-]{11})", raw)
    if m:
        video_id = m.group(1)
    elif re.match(r"^[0-9A-Za-z_-]{11}$", raw):
        video_id = raw
    try:
        data = await _extract_hls(video_id)
        hls = data.get("hls_url") or ""
        if not hls:
            return {
                "parse": 1,
                "url": "https://www.youtube.com/watch?v=%s" % video_id,
            }
        return {
            "parse": 0,
            "url": hls,
            "header": HEADERS,
            "format": "application/x-mpegURL",
        }
    except Exception as e:
        await OmniBox.log("error", "[play] %s" % e)
        return {"parse": 1, "url": "https://www.youtube.com/watch?v=%s" % video_id}


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
