# -*- coding: utf-8 -*-
# @name 熊猫聚合
# @version 1.2.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%9B%B4%E6%92%AD%E5%B9%B3%E5%8F%B0/熊猫聚合.py
# @description PandaLive 聚合源：代理+直链；播放时按 uid 刷新 m3u8

"""
熊猫聚合 — OmniBox v1.0.0

来源脚本: TG @tvshare23 类 T3 Spider 适配
数据: https://5721004.xyz/player/list.m3u + list.json
播放: 代理拼接 m3u8（CDN 直连常 403）
说明: 与「熊猫直播」官方源互不影响，本源只含 M3U 有流的房间
"""

import json
import random
import re
import time

from spider_runner import OmniBox, run

HOST = "https://5721004.xyz"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Referer": "https://www.pandalive.co.kr/",
    "Origin": "https://www.pandalive.co.kr",
}
PROXIES = [
    "https://hubu.515355.xyz/proxy/?",
    "https://pol.515355.xyz/proxy/",
    "https://f00.515355.xyz/proxy/",
    "https://ce2.515355.xyz/proxy/?",
]

CLASSES = [
    {"type_id": "all", "type_name": "全部"},
    {"type_id": "adult", "type_name": "成人"},
    {"type_id": "pw", "type_name": "密码房"},
    {"type_id": "fan", "type_name": "粉丝房"},
    {"type_id": "recorded", "type_name": "录播"},
    {"type_id": "live", "type_name": "直播"},
]


def _page(v):
    try:
        return max(1, int(v))
    except (ValueError, TypeError):
        return 1


async def _get_text(url, timeout=12):
    res = await OmniBox.request(
        url, {"method": "GET", "headers": HEADERS, "timeout": timeout}
    )
    body = res.get("body")
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="ignore")
    return str(body or ""), int(res.get("statusCode") or 0)


async def _get_json(url, timeout=12):
    text, status = await _get_text(url, timeout=timeout)
    if not text or text[:1] == "<":
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


async def _load_m3u():
    cache_key = "panda_agg_m3u_v1"
    try:
        cached = await OmniBox.getCache(cache_key)
        if isinstance(cached, dict) and cached.get("map"):
            return cached["map"]
    except Exception:
        pass

    text, status = await _get_text(HOST + "/player/list.m3u")
    m = {}
    if not status or status < 400:
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if not line.startswith("#EXTINF") or i + 1 >= len(lines):
                continue
            stream = lines[i + 1].strip()
            if not stream.startswith("http"):
                continue
            parts = line.split(",")
            uid = parts[1].strip() if len(parts) >= 2 else ""
            nick_meta = parts[2].strip() if len(parts) > 2 else ""
            if not uid:
                continue
            tags = re.findall(r"\[([^\]]+)\]", nick_meta)
            m[uid] = {
                "url": stream,
                "tags": tags,
                "nick": re.sub(r"\[[^\]]*\]", "", nick_meta).strip() or uid,
                "is_recorded": "录" in tags,
                "is_fan": "粉" in tags,
            }
    try:
        await OmniBox.setCache(
            cache_key, {"expiresAt": int(time.time()) + 45, "map": m}
        )
    except Exception:
        pass
    return m


async def _load_list():
    cache_key = "panda_agg_list_v1"
    try:
        cached = await OmniBox.getCache(cache_key)
        if isinstance(cached, dict) and isinstance(cached.get("list"), list) and cached["list"]:
            return cached["list"]
    except Exception:
        pass

    m3u = await _load_m3u()
    if not m3u:
        return []

    data = await _get_json(HOST + "/player/list.json")
    raw = data.get("list") if isinstance(data, dict) else []
    if not isinstance(raw, list):
        raw = []
    by_uid = {
        str(it.get("userId")): it
        for it in raw
        if isinstance(it, dict) and it.get("userId")
    }

    processed = []
    for uid, meta in m3u.items():
        match = by_uid.get(uid)
        if not match:
            match = {
                "userId": uid,
                "userNick": meta.get("nick") or uid,
                "title": meta.get("nick") or uid,
                "isAdult": False,
                "isPw": False,
                "type": "fan" if meta.get("is_fan") else "free",
                "user": 0,
                "thumbUrl": "",
                "isLive": True,
                "totalScoreCnt": 0,
                "bookmarkCnt": 0,
            }
        if match.get("isLive") is False:
            continue
        nick = match.get("userNick") or meta.get("nick") or uid
        title = match.get("title") or "LIVE"
        is_adult = bool(match.get("isAdult"))
        is_pw = bool(match.get("isPw"))
        v_type = str(match.get("type") or "")
        try:
            user_count = int(match.get("user") or 0)
        except Exception:
            user_count = 0
        thumb = match.get("thumbUrl") or match.get("ivsThumbnail") or ""
        tags = list(meta.get("tags") or [])
        if is_adult:
            tags.append("19+")
        tag_str = " ".join("[%s]" % t for t in tags)
        if user_count >= 10000:
            online = "%.1f万" % (user_count / 10000.0)
        else:
            online = str(user_count)
        processed.append(
            {
                "vod_id": uid,
                "vod_name": nick,
                "vod_pic": thumb,
                "vod_remarks": "观众%s %s" % (online, tag_str),
                "vod_content": title,
                "vod_actor": uid,
                "_isAdult": is_adult,
                "_isPw": is_pw,
                "_type": v_type,
                "_isRecorded": bool(meta.get("is_recorded")),
                "_isFan": bool(meta.get("is_fan")) or v_type == "fan",
                "_user_count": user_count,
                "_score": int(match.get("totalScoreCnt") or 0),
                "_bookmark": int(match.get("bookmarkCnt") or 0),
                "_stream": meta.get("url") or "",
            }
        )

    try:
        await OmniBox.setCache(
            cache_key, {"expiresAt": int(time.time()) + 40, "list": processed}
        )
    except Exception:
        pass
    return processed


def _filter_sort(items, tid):
    filtered = list(items)
    if tid == "adult":
        filtered = [v for v in filtered if v.get("_isAdult")]
    elif tid == "pw":
        filtered = [v for v in filtered if v.get("_isPw")]
    elif tid == "fan":
        filtered = [v for v in filtered if v.get("_isFan") or v.get("_type") == "fan"]
    elif tid == "recorded":
        filtered = [v for v in filtered if v.get("_isRecorded")]
    elif tid == "live":
        filtered = [v for v in filtered if not v.get("_isRecorded")]
    filtered.sort(key=lambda x: x.get("_user_count") or 0, reverse=True)
    return filtered


def _card(v):
    return {
        "vod_id": v.get("vod_id"),
        "vod_name": v.get("vod_name"),
        "vod_pic": v.get("vod_pic"),
        "vod_remarks": v.get("vod_remarks"),
    }


async def home(params, context):
    try:
        all_data = await _load_list()
        cards = [_card(v) for v in all_data[:40]]
        await OmniBox.log("info", "[熊猫聚合][home] n=%s" % len(all_data))
        return {"class": CLASSES, "list": cards, "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[熊猫聚合][home] %s" % e)
        return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    tid = str(
        (params or {}).get("categoryId")
        or (params or {}).get("type_id")
        or (params or {}).get("tid")
        or "all"
    )
    page = _page((params or {}).get("page") or (params or {}).get("pg") or 1)
    try:
        all_list = await _load_list()
        filtered = _filter_sort(all_list, tid)
        limit = 30
        start = (page - 1) * limit
        page_list = filtered[start : start + limit]
        pagecount = max(1, (len(filtered) + limit - 1) // limit)
        return {
            "list": [_card(v) for v in page_list],
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": len(filtered),
        }
    except Exception as e:
        await OmniBox.log("error", "[熊猫聚合][category] %s" % e)
        return {"list": [], "page": page, "pagecount": page, "total": 0}


async def search(params, context):
    key = str(
        (params or {}).get("keyword")
        or (params or {}).get("wd")
        or (params or {}).get("key")
        or ""
    ).strip()
    page = _page((params or {}).get("page") or 1)
    if not key:
        return {"list": [], "page": page, "pagecount": 0, "total": 0}
    try:
        all_v = await _load_list()
        key_l = key.lower()
        res = [
            v
            for v in all_v
            if key_l in (v.get("vod_name") or "").lower()
            or key_l in (v.get("vod_id") or "").lower()
            or key_l in (v.get("vod_content") or "").lower()
        ]
        return {
            "list": [_card(v) for v in res[:50]],
            "page": page,
            "pagecount": 1,
            "total": len(res),
        }
    except Exception as e:
        await OmniBox.log("error", "[熊猫聚合][search] %s" % e)
        return {"list": [], "page": page, "pagecount": 0, "total": 0}


async def detail(params, context):
    p = params or {}
    vid = str(
        p.get("videoId") or p.get("vodId") or p.get("id") or p.get("ids") or ""
    ).strip()
    if not vid:
        return {"list": []}
    uid = vid.replace("live_", "").strip()
    try:
        all_list = await _load_list()
        info = None
        for v in all_list:
            if v.get("vod_id") == uid or v.get("vod_id") == vid:
                info = v
                break
        m3u = await _load_m3u()
        meta = m3u.get(uid)
        if not meta and not info:
            return {"list": []}
        stream = (meta or {}).get("url") or (info or {}).get("_stream") or ""
        name = (info or {}).get("vod_name") or (meta or {}).get("nick") or uid
        pic = (info or {}).get("vod_pic") or ""
        content = (info or {}).get("vod_content") or ("主播: %s" % uid)
        remarks = (info or {}).get("vod_remarks") or (
            "录播" if (meta or {}).get("is_recorded") else "直播"
        )

        episodes = []
        # 代理 + 直链；playId 只带 uid，播放时重取最新 m3u8
        if stream or meta:
            order = list(range(len(PROXIES)))
            random.shuffle(order)
            for n, idx in enumerate(order, 1):
                episodes.append({"name": "代理%s" % n, "playId": "p%s|%s" % (idx, uid)})
            episodes.append({"name": "直链", "playId": "direct|%s" % uid})

        await OmniBox.log(
            "info", "[熊猫聚合][detail] uid=%s ep=%s" % (uid, len(episodes))
        )
        return {
            "list": [
                {
                    "vod_id": uid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remarks,
                    "vod_content": content,
                    "vod_actor": uid,
                    "vod_play_sources": [{"name": "熊猫聚合", "episodes": episodes}]
                    if episodes
                    else [],
                }
            ]
        }
    except Exception as e:
        await OmniBox.log("error", "[熊猫聚合][detail] %s" % e)
        return {"list": []}



async def _fresh_stream(uid):
    """播放前强制重拉 M3U，拿到未过期的 m3u8。"""
    uid = (uid or "").replace("live_", "").strip()
    if not uid:
        return ""
    try:
        await OmniBox.setCache("panda_agg_m3u_v1", {"expiresAt": 0, "map": {}})
        await OmniBox.setCache("panda_agg_list_v1", {"expiresAt": 0, "list": []})
    except Exception:
        pass
    m3u = await _load_m3u()
    meta = m3u.get(uid) or {}
    return str(meta.get("url") or "").strip()


def _proxy_url(proxy, stream):
    """拼接代理；对 query 做必要编码，减少个别房间失败。"""
    from urllib.parse import quote
    stream = str(stream or "").strip()
    if not stream:
        return ""
    # 已是完整代理地址则直接返回
    if "515355.xyz/proxy" in stream:
        return stream
    if proxy.endswith("?") or proxy.endswith("&"):
        return proxy + quote(stream, safe=":/?&=%#._~")
    if proxy.endswith("/"):
        return proxy + quote(stream, safe=":/?&=%#._~")
    return proxy + quote(stream, safe=":/?&=%#._~")


async def play(params, context):
    play_id = str(
        (params or {}).get("playId")
        or (params or {}).get("id")
        or (params or {}).get("videoId")
        or ""
    ).strip()
    if not play_id:
        return {"urls": [], "parse": 0, "header": HEADERS}
    try:
        kind, uid = "auto", play_id
        if "|" in play_id:
            kind, uid = play_id.split("|", 1)
        uid = uid.replace("live_", "").strip()
        # 兼容旧版：playId 后半段是整段 http
        if uid.startswith("http"):
            stream = uid
            uid = ""
        else:
            stream = await _fresh_stream(uid)

        if not stream.startswith("http"):
            await OmniBox.log("warn", "[熊猫聚合][play] 无流 uid=%s" % (uid or play_id))
            return {"urls": [], "parse": 0, "header": HEADERS}

        urls = []
        if kind == "direct":
            urls.append({"name": "直链", "url": stream})
            # 直链常 403，附带代理作备选
            for i, pxy in enumerate(PROXIES):
                urls.append({"name": "代理%s" % (i + 1), "url": _proxy_url(pxy, stream)})
        else:
            idx = -1
            k = kind[1:] if str(kind).startswith("p") else kind
            try:
                idx = int(k)
            except Exception:
                idx = -1
            ordered = list(range(len(PROXIES)))
            if 0 <= idx < len(PROXIES):
                ordered = [idx] + [i for i in ordered if i != idx]
            for i in ordered:
                urls.append({"name": "代理%s" % (i + 1), "url": _proxy_url(PROXIES[i], stream)})

        await OmniBox.log(
            "info", "[熊猫聚合][play] uid=%s proxies=%s" % (uid or "-", len(urls))
        )
        return {
            "urls": urls,
            "parse": 0,
            "header": HEADERS,
            "extra": {"live": True},
        }
    except Exception as e:
        await OmniBox.log("error", "[熊猫聚合][play] %s" % e)
        return {"urls": [], "parse": 0, "header": HEADERS}


run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
