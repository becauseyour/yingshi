# -*- coding: utf-8 -*-
# @name 斗鱼直播
# @version 1.0.0
# @description 斗鱼直播 OmniBox 源：仅展示在线直播间 / 分类 / 搜索 / 播放
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%9B%B4%E6%92%AD%E5%B9%B3%E5%8F%B0/斗鱼.py
import re
from urllib.parse import quote

from spider_runner import OmniBox, run

HOST = "https://www.douyu.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# 常用分类 (cid2 或 mixList 路径)
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


async def _get_json(url, referer=HOST + "/"):
    res = await OmniBox.request(
        url,
        {
            "method": "GET",
            "headers": {
                "User-Agent": UA,
                "Referer": referer,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            "timeout": 12,
        },
    )
    status = int(res.get("statusCode") or 0)
    body = res.get("body")
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="ignore")
    text = str(body or "")
    if status and (status < 200 or status >= 400):
        raise IOError("HTTP %s" % status)
    return json.loads(text) if text else {}


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
    online = _fmt_online(item.get("ol") or item.get("online") or 0)
    game = item.get("c2name") or item.get("game_name") or ""
    remark = "%s · %s" % (game, online) if game else online
    return {
        "vod_id": rid,
        "vod_name": title,
        "vod_pic": pic,
        "vod_remarks": remark,
    }


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
    tid = str(params.get("categoryId") or params.get("type_id") or params.get("tid") or "0_0")
    page = _page(params.get("page") or params.get("pg") or 1)
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
    keyword = str(params.get("keyword") or params.get("wd") or params.get("key") or "").strip()
    page = _page(params.get("page") or params.get("pg") or 1)
    if not keyword:
        return {"list": [], "page": page, "pagecount": page, "total": 0}
    try:
        # 斗鱼搜索
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
            if int(room.get("online") or room.get("ol") or 0) <= 0 and str(
                room.get("show_status") or ""
            ) not in ("1", "2"):
                # 仍尝试加入有标题的
                if not (room.get("room_name") or room.get("rn")):
                    continue
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
    rid = str(params.get("vodId") or params.get("id") or params.get("ids") or "").strip()
    if not rid:
        return {"list": []}
    try:
        # 房间信息
        url = "https://www.douyu.com/betard/%s" % rid
        data = await _get_json(url, referer=HOST + "/" + rid)
        room = (data.get("room") or data.get("data") or {}) if isinstance(data, dict) else {}
        if not room:
            # 再试 open api
            url2 = "https://open.douyucdn.cn/api/RoomApi/room/%s" % rid
            data2 = await _get_json(url2)
            room = data2.get("data") or {}

        title = room.get("room_name") or room.get("rn") or ("斗鱼 " + rid)
        pic = room.get("room_src") or room.get("room_pic") or ""
        if pic.startswith("//"):
            pic = "https:" + pic
        online = _fmt_online(room.get("online") or room.get("hn") or 0)
        owner = room.get("nickname") or room.get("owner_name") or room.get("nn") or ""
        game = room.get("cate_name") or room.get("game_name") or ""
        status = str(room.get("show_status") or room.get("status") or "")
        is_live = status in ("1", "2") or int(room.get("online") or 0) > 0
        content = "主播: %s\n分区: %s\n人气: %s\n状态: %s" % (
            owner,
            game,
            online,
            "直播中" if is_live else "未开播",
        )
        episodes = [{"name": "直播中", "playId": rid}] if is_live else []
        await OmniBox.log("info", "[斗鱼][detail] rid=%s live=%s" % (rid, is_live))
        return {
            "list": [
                {
                    "vod_id": rid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "%s · %s" % (game, online),
                    "vod_content": content,
                    "vod_play_sources": [{"name": "斗鱼直播", "episodes": episodes}],
                }
            ]
        }
    except Exception as e:
        await OmniBox.log("error", "[斗鱼][detail] %s" % e)
        return {"list": []}


async def play(params, context):
    rid = str(params.get("playId") or params.get("id") or "").strip()
    if not rid:
        return {"urls": [], "parse": 0, "header": {}}
    headers = {"User-Agent": UA, "Referer": HOST + "/" + rid}
    try:
        # 先确认在线
        info = await _get_json("https://www.douyu.com/betard/%s" % rid, referer=HOST + "/" + rid)
        room = info.get("room") or {}
        status = str(room.get("show_status") or "")
        if status not in ("1", "2") and int(room.get("online") or 0) <= 0:
            await OmniBox.log("info", "[斗鱼][play] offline rid=%s" % rid)
            return {"urls": [], "parse": 0, "header": headers}

        # 尝试 H5 播放接口（部分房间可用）
        play_api = "https://www.douyu.com/lapi/live/getH5Play/%s" % rid
        # 无签名时可能失败，失败则走网页解析
        try:
            pdata = await _get_json(play_api, referer=HOST + "/" + rid)
            if pdata.get("error") == 0 and pdata.get("data"):
                d = pdata["data"]
                rtmp = d.get("rtmp_url") or ""
                live = d.get("rtmp_live") or ""
                if rtmp and live:
                    full = rtmp.rstrip("/") + "/" + live
                    return {
                        "urls": [{"name": "原画", "url": full}],
                        "parse": 0,
                        "header": headers,
                    }
        except Exception:
            pass

        # 兜底网页
        return {
            "urls": [{"name": "网页", "url": HOST + "/" + rid}],
            "parse": 1,
            "header": headers,
        }
    except Exception as e:
        await OmniBox.log("error", "[斗鱼][play] %s" % e)
        return {
            "urls": [{"name": "网页", "url": HOST + "/" + rid}],
            "parse": 1,
            "header": headers,
        }


run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
