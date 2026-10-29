# -*- coding: utf-8 -*-
# @name 咖啡直播
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%9B%B4%E6%92%AD%E5%B9%B3%E5%8F%B0/咖啡直播.py
# @description 体育赛事直播+录像回放（足球/篮球/NBA）；直播仅展示在线房间

"""
咖啡直播 — OmniBox v1.0.0
站点: https://kafeizhibo.com
直播: GET /api/v1/archor  详情 /api/v1/room/{room_id}
录像: GET /api/v1/recordings  详情 /api/v1/match/{id}/recordings
"""

import json
from urllib.parse import quote

from spider_runner import OmniBox, run

HOST = "https://kafeizhibo.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
)

CLASSES = [
    {"type_id": "live_all", "type_name": "🔴 直播全部"},
    {"type_id": "live_1", "type_name": "🔴 直播足球"},
    {"type_id": "live_2", "type_name": "🔴 直播篮球"},
    {"type_id": "all", "type_name": "录像全部"},
    {"type_id": "1", "type_name": "录像足球"},
    {"type_id": "2", "type_name": "录像篮球"},
    {"type_id": "nba", "type_name": "录像NBA"},
]


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _norm_url(path):
    if not path:
        return ""
    if path.startswith("http"):
        return path
    if path.startswith("//"):
        return "https:" + path
    return HOST + ("" if path.startswith("/") else "/") + path


async def _get_json(path, referer=None, params=None):
    url = HOST + path
    if params:
        qs = "&".join("%s=%s" % (k, quote(str(v))) for k, v in params.items())
        url = url + ("&" if "?" in url else "?") + qs
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Referer": referer or (HOST + "/live/all"),
        "Origin": HOST,
    }
    res = await OmniBox.request(url, {"method": "GET", "headers": headers, "timeout": 12})
    text = (res.get("body") or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


def _parse_live_list(items, category_filter=None):
    """仅 status online 的房间；按 room_id 去重。"""
    seen = set()
    result = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        if category_filter is not None and item.get("category") != category_filter:
            continue
        status = str(item.get("status") or "").lower()
        if status and status not in ("online", "1", "live", "on"):
            # 列表接口本身是在播频道，无 status 也保留
            if status in ("offline", "off", "0", "end"):
                continue
        room_id = str(item.get("room_id") or "").strip()
        if not room_id or room_id in seen:
            continue
        seen.add(room_id)
        home = item.get("home_team") or ""
        away = item.get("away_team") or ""
        league = item.get("league_name") or ""
        if home or away:
            title = "%s vs %s (%s)" % (home, away, league)
        else:
            title = str(item.get("title") or item.get("name") or room_id)
        h_score = item.get("home_score", 0)
        a_score = item.get("away_score", 0)
        pic = _norm_url(item.get("screenshot") or "")
        if not pic or "default" in pic:
            mi = item.get("match_info") or {}
            pic = mi.get("home_team_logo") or ""
        result.append(
            {
                "vod_id": "live_%s" % room_id,
                "vod_name": "🔴 " + title,
                "vod_pic": pic,
                "vod_remarks": "%s-%s | %s" % (h_score, a_score, item.get("name") or "直播"),
            }
        )
    return result


def _parse_video_list(items):
    result = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        mid = item.get("match_id")
        if mid is None:
            continue
        title = "%s vs %s (%s)" % (
            item.get("home_team") or "",
            item.get("away_team") or "",
            item.get("league_name") or "",
        )
        score = "%s-%s" % (item.get("home_score", 0), item.get("away_score", 0))
        pic = item.get("cover_image") or ""
        if pic and not str(pic).startswith("http"):
            pic = _norm_url(pic)
        if not pic or "default_cover" in str(pic):
            pic = item.get("home_team_logo") or ""
        result.append(
            {
                "vod_id": str(mid),
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "%s | %s | %s个录像"
                % (score, item.get("start_time") or "", item.get("recording_count") or 0),
            }
        )
    return result


async def _detail_live(room_id):
    data = await _get_json(
        "/api/v1/room/%s" % room_id,
        referer=HOST + "/room/%s" % room_id,
    )
    if data.get("code") != 200 or not data.get("data"):
        return {"list": []}
    d = data["data"]
    room_info = d.get("room_info") or {}
    signals = d.get("signals") or []
    home = room_info.get("home_team") or ""
    away = room_info.get("away_team") or ""
    league = room_info.get("league") or room_info.get("league_name") or ""
    title = "%s vs %s (%s)" % (home, away, league) if (home or away) else ("直播 %s" % room_id)
    teams = d.get("teams") or {}
    pic = ((teams.get("home") or {}).get("logo")) or ""
    episodes = []
    for sig in signals:
        url = (sig.get("stream_url") or "").strip()
        if url:
            episodes.append("%s$%s" % (sig.get("name") or "线路", url))
    if not episodes:
        archor = d.get("archor") or {}
        url = (archor.get("stream_url") or "").strip()
        if url:
            episodes.append("%s$%s" % (archor.get("name") or "直播", url))
    if not episodes:
        return {"list": []}
    vod = {
        "vod_id": "live_%s" % room_id,
        "vod_name": "🔴 " + title,
        "vod_pic": pic,
        "vod_content": "%s %s vs %s 比分 %s-%s"
        % (league, home, away, room_info.get("home_score", 0), room_info.get("away_score", 0)),
        "vod_play_from": "直播线路",
        "vod_play_url": "#".join(episodes),
    }
    return {"list": [vod]}


async def _detail_recording(vid):
    data = await _get_json(
        "/api/v1/match/%s/recordings" % vid,
        referer=HOST + "/pc/replay",
    )
    if data.get("code") != 200 or not data.get("data"):
        return {"list": []}
    match = (data["data"].get("match") or {})
    replays = data["data"].get("replays") or []
    highlights = data["data"].get("highlights") or []
    title = "%s vs %s (%s)" % (
        match.get("home_team") or "",
        match.get("away_team") or "",
        match.get("league_name") or "",
    )
    pic = match.get("home_team_logo") or match.get("away_team_logo") or ""
    episodes = []
    for idx, rec in enumerate(replays):
        url = (rec.get("video_url") or "").strip()
        if url:
            episodes.append("%s$%s" % (rec.get("title") or ("录像%s" % (idx + 1)), url))
    for idx, rec in enumerate(highlights):
        url = (rec.get("video_url") or "").strip()
        if url:
            episodes.append("%s$%s" % (rec.get("title") or ("集锦%s" % (idx + 1)), url))
    if not episodes:
        return {"list": []}
    vod = {
        "vod_id": str(vid),
        "vod_name": title,
        "vod_pic": pic,
        "vod_content": "%s %s vs %s 比分 %s-%s 时间 %s"
        % (
            match.get("league_name") or "",
            match.get("home_team") or "",
            match.get("away_team") or "",
            match.get("home_score", 0),
            match.get("away_score", 0),
            match.get("start_time") or "",
        ),
        "vod_play_from": "录像源",
        "vod_play_url": "#".join(episodes),
    }
    return {"list": [vod]}


async def home(params, context):
    try:
        data = await _get_json("/api/v1/archor")
        vod_list = _parse_live_list(data.get("data") or []) if data.get("code") == 200 else []
        return {"class": CLASSES, "list": vod_list, "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[home] %s" % e)
        return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    tid = str((params or {}).get("categoryId") or "live_all")
    page = _to_int((params or {}).get("page"), 1) or 1
    try:
        if tid in ("live_all", "live_1", "live_2"):
            data = await _get_json("/api/v1/archor")
            cat = None if tid == "live_all" else _to_int(tid.split("_")[1])
            vod_list = (
                _parse_live_list(data.get("data") or [], category_filter=cat)
                if data.get("code") == 200
                else []
            )
            return {
                "list": vod_list,
                "page": 1,
                "pagecount": 1,
                "limit": 100,
                "total": len(vod_list),
            }

        if tid == "nba":
            data = await _get_json(
                "/api/v1/recordings",
                referer=HOST + "/pc/replay",
                params={"page": page, "size": 20, "league": "NBA"},
            )
            size = 20
        elif tid == "all":
            data = await _get_json(
                "/api/v1/recordings",
                referer=HOST + "/pc/replay",
                params={"page": page, "size": 30},
            )
            size = 30
        else:
            data = await _get_json(
                "/api/v1/recordings",
                referer=HOST + "/pc/replay",
                params={"page": page, "size": 30, "type": tid},
            )
            size = 30

        vod_list = []
        pagecount = page
        if data.get("code") == 200 and data.get("data"):
            vod_list = _parse_video_list(data["data"])
            pagecount = page + 1 if len(data["data"]) >= size else page
        return {
            "list": vod_list,
            "page": page,
            "pagecount": pagecount,
            "limit": size,
            "total": pagecount * size,
        }
    except Exception as e:
        await OmniBox.log("error", "[category] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "limit": 30, "total": 0}


async def detail(params, context):
    vid = str((params or {}).get("videoId") or "").strip()
    if not vid:
        return {"list": []}
    try:
        if vid.startswith("live_"):
            return await _detail_live(vid[5:])
        return await _detail_recording(vid)
    except Exception as e:
        await OmniBox.log("error", "[detail] %s" % e)
        return {"list": []}


async def search(params, context):
    key = str((params or {}).get("keyword") or "").strip()
    if not key:
        return {"list": []}
    keyword = key.lower()
    result = []
    try:
        data = await _get_json("/api/v1/archor")
        if data.get("code") == 200:
            for item in data.get("data") or []:
                blob = " ".join(
                    str(item.get(k) or "")
                    for k in ("home_team", "away_team", "league_name", "title", "name")
                ).lower()
                if keyword not in blob:
                    continue
                room_id = str(item.get("room_id") or "")
                if not room_id:
                    continue
                home = item.get("home_team") or ""
                away = item.get("away_team") or ""
                league = item.get("league_name") or ""
                result.append(
                    {
                        "vod_id": "live_%s" % room_id,
                        "vod_name": "🔴 %s vs %s (%s)" % (home, away, league),
                        "vod_pic": "",
                        "vod_remarks": "直播中",
                    }
                )
    except Exception as e:
        await OmniBox.log("error", "[search live] %s" % e)
    try:
        data = await _get_json(
            "/api/v1/recordings",
            referer=HOST + "/pc/replay",
            params={"page": 1, "size": 100},
        )
        if data.get("code") == 200:
            for item in data.get("data") or []:
                blob = " ".join(
                    str(item.get(k) or "")
                    for k in ("home_team", "away_team", "league_name")
                ).lower()
                if keyword not in blob:
                    continue
                result.append(
                    {
                        "vod_id": str(item.get("match_id")),
                        "vod_name": "%s vs %s (%s)"
                        % (
                            item.get("home_team") or "",
                            item.get("away_team") or "",
                            item.get("league_name") or "",
                        ),
                        "vod_pic": "",
                        "vod_remarks": "%s-%s"
                        % (item.get("home_score", 0), item.get("away_score", 0)),
                    }
                )
    except Exception as e:
        await OmniBox.log("error", "[search rec] %s" % e)
    return {"list": result, "page": 1, "pagecount": 1}


async def play(params, context):
    """播放地址已在 detail 的 vod_play_url 中，这里直接回传。"""
    url = str((params or {}).get("url") or (params or {}).get("flag") or "").strip()
    # OmniBox 有时把集数名后的真实地址放在 url / playUrl
    play_url = str(
        (params or {}).get("playUrl")
        or (params or {}).get("url")
        or (params or {}).get("id")
        or ""
    ).strip()
    if "$" in play_url:
        play_url = play_url.split("$", 1)[-1]
    if not play_url.startswith("http"):
        play_url = url if url.startswith("http") else play_url
    header = {
        "User-Agent": UA,
        "Referer": HOST + "/",
        "Origin": HOST,
    }
    return {
        "parse": 0,
        "url": play_url,
        "header": header,
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
