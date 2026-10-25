# -*- coding: utf-8 -*-
# @name 斗鱼直播
# @version 1.1.0
# @description 斗鱼直播 OmniBox 源：仅展示在线直播间；修复详情 videoId / 播放取流
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%9B%B4%E6%92%AD%E5%B9%B3%E5%8F%B0/斗鱼.py
import hashlib
import json
import re
import time
from urllib.parse import quote

from spider_runner import OmniBox, run

HOST = "https://www.douyu.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

CLASSES = [
    {"type_id": "0_0", "type_name": "全部热门"},
    {"type_id": "2_1", "type_name": "英雄联盟"},
    {"type_id": "2_270", "type_name": "王者荣耀"},
    {"type_id": "2_181", "type_name": "绝地求生"},
    {"type_id": "2_174", "type_name": "主机游戏"},
    {"type_id": "2_201", "type_name": "颜值"},
    {"type_id": "2_33", "type_name": "户外"},
    {"type_id": "2_124", "type_name": "音乐"},
    {"type_id": "2_2", "type_name": "游戏"},
    {"type_id": "2_1008", "type_name": "一起看"},
]


def _page(v):
    try:
        return max(1, int(v))
    except (ValueError, TypeError):
        return 1


def _rid(params):
    p = params or {}
    for k in ("videoId", "vodId", "playId", "id", "ids"):
        v = str(p.get(k) or "").strip()
        if v:
            return v.split("|")[0].strip()
    return ""


async def _request(url, method="GET", body=None, referer=HOST + "/", extra_headers=None):
    headers = {
        "User-Agent": UA,
        "Referer": referer,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    if extra_headers:
        headers.update(extra_headers)
    opts = {"method": method, "headers": headers, "timeout": 12}
    if body is not None:
        opts["body"] = body
    res = await OmniBox.request(url, opts)
    status = int(res.get("statusCode") or 0)
    body_r = res.get("body")
    if isinstance(body_r, bytes):
        body_r = body_r.decode("utf-8", errors="ignore")
    text = str(body_r or "")
    return status, text


async def _get_json(url, referer=HOST + "/"):
    status, text = await _request(url, referer=referer)
    if status and (status < 200 or status >= 400):
        raise IOError("HTTP %s" % status)
    if not text or text[:1] == "<":
        return {}
    return json.loads(text)


def _fmt_online(n):
    try:
        n = int(n)
    except Exception:
        return str(n or "")
    if n >= 10000:
        return "%.1f万" % (n / 10000)
    return str(n)


def _room_item(item):
    rid = str(item.get("rid") or item.get("room_id") or "").strip()
    if not rid:
        return None
    title = (item.get("rn") or item.get("room_name") or item.get("nn") or "").strip()
    if not title:
        title = item.get("nn") or rid
    pic = item.get("rs16") or item.get("room_src") or item.get("av") or ""
    if pic and not pic.startswith("http"):
        if pic.startswith("//"):
            pic = "https:" + pic
        else:
            pic = "https://rpic.douyucdn.cn/" + pic.lstrip("/")
    if pic.startswith("//"):
        pic = "https:" + pic
    online = _fmt_online(item.get("ol") or item.get("online") or 0)
    game = item.get("c2name") or item.get("game_name") or ""
    remark = "%s · %s" % (game, online) if game else online
    return {
        "vod_id": rid,
        "vod_name": title,
        "vod_pic": pic,
        "vod_remarks": remark,
    }


async def _room_info(rid):
    """聚合房间信息：betard + open api。"""
    room = {}
    try:
        data = await _get_json(
            "https://www.douyu.com/betard/%s" % rid, referer=HOST + "/" + rid
        )
        room = data.get("room") or {}
        if not isinstance(room, dict):
            room = {}
    except Exception:
        room = {}
    if not room.get("room_name") and not room.get("show_status"):
        try:
            data2 = await _get_json(
                "https://open.douyucdn.cn/api/RoomApi/room/%s" % rid,
                referer=HOST + "/",
            )
            d = data2.get("data") or {}
            if d:
                room = {
                    "room_id": d.get("room_id") or rid,
                    "room_name": d.get("room_name"),
                    "nickname": d.get("owner_name"),
                    "room_src": d.get("room_thumb"),
                    "online": d.get("online") or d.get("hn"),
                    "cate_name": d.get("cate_name"),
                    "show_status": d.get("room_status") or d.get("show_status"),
                }
        except Exception:
            pass
    return room


def _is_live(room):
    if not isinstance(room, dict):
        return False
    status = str(room.get("show_status") or room.get("room_status") or room.get("status") or "")
    if status in ("1", "2"):
        return True
    try:
        if int(room.get("online") or room.get("hn") or 0) > 0:
            return True
    except Exception:
        pass
    return False


async def _play_h5(rid):
    """尝试多组 H5 取流（部分房间/时段可用）。"""
    tt = str(int(time.time()))
    auth = hashlib.md5(("room" + rid + tt + "zNzMVNouhkLCJQUn").encode("utf-8")).hexdigest()
    endpoints = [
        "https://www.douyu.com/lapi/live/getH5Play/%s" % rid,
        "https://playweb.douyucdn.cn/lapi/live/getH5Play/%s" % rid,
    ]
    body = "rid=%s&rate=0" % rid
    headers_extra = {
        "Content-Type": "application/x-www-form-urlencoded",
        "rid": rid,
        "time": tt,
        "auth": auth,
    }
    for url in endpoints:
        try:
            status, text = await _request(
                url,
                method="POST",
                body=body,
                referer=HOST + "/" + rid,
                extra_headers=headers_extra,
            )
            if not text or text[:1] == "<":
                continue
            data = json.loads(text)
            if int(data.get("error") or -1) != 0:
                continue
            d = data.get("data") or {}
            rtmp = str(d.get("rtmp_url") or "").rstrip("/")
            live = str(d.get("rtmp_live") or "")
            if rtmp and live:
                return rtmp + "/" + live
            for k in ("hls_url", "rtmp_cdn", "url"):
                u = d.get(k)
                if isinstance(u, str) and u.startswith("http"):
                    return u
        except Exception:
            continue
    return ""


async def home(params, context):
    try:
        data = await _get_json(HOST + "/gapi/rkc/directory/mixList/0_0/1")
        rl = (data.get("data") or {}).get("rl") or []
        cards = []
        for it in rl[:48]:
            if int(it.get("ol") or 0) <= 0:
                continue
            card = _room_item(it)
            if card:
                cards.append(card)
        await OmniBox.log("info", "[斗鱼][home] list=%s" % len(cards))
        return {"class": CLASSES, "list": cards}
    except Exception as e:
        await OmniBox.log("error", "[斗鱼][home] %s" % e)
        return {"class": CLASSES, "list": []}


async def category(params, context):
    tid = str(
        (params or {}).get("categoryId")
        or (params or {}).get("type_id")
        or (params or {}).get("tid")
        or "0_0"
    )
    page = _page((params or {}).get("page") or (params or {}).get("pg") or 1)
    try:
        url = HOST + "/gapi/rkc/directory/mixList/%s/%s" % (tid, page)
        data = await _get_json(url)
        d = data.get("data") or {}
        rl = d.get("rl") or []
        cards = []
        for it in rl:
            if int(it.get("ol") or 0) <= 0:
                continue
            card = _room_item(it)
            if card:
                cards.append(card)
        pgcnt = int(d.get("pgcnt") or page)
        await OmniBox.log(
            "info", "[斗鱼][category] tid=%s page=%s list=%s" % (tid, page, len(cards))
        )
        return {
            "list": cards,
            "page": page,
            "pagecount": max(pgcnt, page),
            "total": len(cards) * max(pgcnt, 1),
        }
    except Exception as e:
        await OmniBox.log("error", "[斗鱼][category] %s" % e)
        return {"list": [], "page": page, "pagecount": page, "total": 0}


async def search(params, context):
    keyword = str(
        (params or {}).get("keyword")
        or (params or {}).get("wd")
        or (params or {}).get("key")
        or ""
    ).strip()
    page = _page((params or {}).get("page") or (params or {}).get("pg") or 1)
    if not keyword:
        return {"list": [], "page": page, "pagecount": page, "total": 0}
    try:
        url = (
            "https://www.douyu.com/japi/search/api/searchLiveInRoom?kw=%s&page=%s&pageSize=20"
            % (quote(keyword), page)
        )
        data = await _get_json(url)
        relate = (data.get("data") or {}).get("relateRoom") or []
        if not relate:
            relate = (data.get("data") or {}).get("list") or []
        cards = []
        for it in relate:
            room = it.get("roomInfo") or it
            card = _room_item(
                {
                    "rid": room.get("rid") or room.get("room_id"),
                    "rn": room.get("room_name") or room.get("rn"),
                    "nn": room.get("nickname") or room.get("nn"),
                    "ol": room.get("online") or room.get("ol") or 0,
                    "av": room.get("avatar") or room.get("room_src"),
                    "c2name": room.get("cateName") or room.get("c2name"),
                }
            )
            if card:
                cards.append(card)
        if not cards and re.match(r"^\d+$", keyword):
            cards.append(
                {
                    "vod_id": keyword,
                    "vod_name": "斗鱼直播间 %s" % keyword,
                    "vod_pic": "",
                    "vod_remarks": "直达",
                }
            )
        await OmniBox.log("info", "[斗鱼][search] key=%s list=%s" % (keyword, len(cards)))
        return {
            "list": cards,
            "page": page,
            "pagecount": page + (1 if len(cards) >= 15 else 0),
            "total": len(cards),
        }
    except Exception as e:
        await OmniBox.log("error", "[斗鱼][search] %s" % e)
        return {"list": [], "page": page, "pagecount": page, "total": 0}


async def detail(params, context):
    rid = _rid(params)
    if not rid:
        return {"list": []}
    try:
        room = await _room_info(rid)
        title = room.get("room_name") or room.get("rn") or ("斗鱼直播间 %s" % rid)
        pic = room.get("room_src") or room.get("room_pic") or ""
        if pic.startswith("//"):
            pic = "https:" + pic
        online = _fmt_online(room.get("online") or room.get("hn") or 0)
        owner = room.get("nickname") or room.get("owner_name") or room.get("nn") or ""
        game = room.get("cate_name") or room.get("game_name") or ""
        is_live = _is_live(room)
        # 列表点进来的默认按在线处理，避免接口字段缺失导致无选集
        if not room:
            is_live = True
        episodes = [{"name": "直播中", "playId": rid}] if is_live else []
        await OmniBox.log("info", "[斗鱼][detail] rid=%s live=%s" % (rid, is_live))
        return {
            "list": [
                {
                    "vod_id": rid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ("%s · %s" % (game, online)).strip(" ·"),
                    "vod_actor": owner,
                    "vod_content": "主播: %s\n分区: %s\n人气: %s" % (owner, game, online),
                    "vod_play_sources": [{"name": "斗鱼直播", "episodes": episodes}],
                }
            ]
        }
    except Exception as e:
        await OmniBox.log("error", "[斗鱼][detail] %s" % e)
        return {
            "list": [
                {
                    "vod_id": rid,
                    "vod_name": "斗鱼直播间 %s" % rid,
                    "vod_pic": "",
                    "vod_play_sources": [
                        {"name": "斗鱼直播", "episodes": [{"name": "直播", "playId": rid}]}
                    ],
                }
            ]
        }


async def play(params, context):
    rid = _rid(params)
    if not rid:
        return {"urls": [], "parse": 0, "header": {}}
    headers = {"User-Agent": UA, "Referer": HOST + "/" + rid}
    try:
        room = await _room_info(rid)
        if room and not _is_live(room):
            await OmniBox.log("info", "[斗鱼][play] offline rid=%s" % rid)
            # 仍尝试取流，避免字段误判

        url = await _play_h5(rid)
        if url:
            await OmniBox.log("info", "[斗鱼][play] got stream rid=%s" % rid)
            return {
                "urls": [{"name": "直播", "url": url}],
                "parse": 0,
                "header": headers,
            }

        # 官方 H5 需签名，失败时回落移动端房间页（客户端可解析/嗅探）
        mobile = "https://m.douyu.com/%s" % rid
        await OmniBox.log("warn", "[斗鱼][play] no direct stream, fallback mobile")
        return {
            "urls": [
                {"name": "移动网页", "url": mobile},
                {"name": "电脑网页", "url": HOST + "/" + rid},
            ],
            "parse": 1,
            "header": headers,
        }
    except Exception as e:
        await OmniBox.log("error", "[斗鱼][play] %s" % e)
        return {
            "urls": [{"name": "移动网页", "url": "https://m.douyu.com/%s" % rid}],
            "parse": 1,
            "header": headers,
        }


run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
