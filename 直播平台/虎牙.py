# -*- coding: utf-8 -*-
# @name 虎牙直播
# @version 1.0.0
# @description 虎牙直播 OmniBox 源：仅展示在线直播间 / 分类 / 搜索 / 播放
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%9B%B4%E6%92%AD%E5%B9%B3%E5%8F%B0/虎牙.py
import json
import re
from urllib.parse import quote

from spider_runner import OmniBox, run

HOST = "https://www.huya.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# 常用分类 (gameId)
CLASSES = [
    {"type_id": "0", "type_name": "全部热门"},
    {"type_id": "1", "type_name": "网游竞技"},
    {"type_id": "2165", "type_name": "户外"},
    {"type_id": "1663", "type_name": "星秀"},
    {"type_id": "2135", "type_name": "一起看"},
    {"type_id": "2336", "type_name": "主机游戏"},
    {"type_id": "2793", "type_name": "美食"},
    {"type_id": "2168", "type_name": "交友"},
    {"type_id": "7601", "type_name": "二次元"},
    {"type_id": "1669", "type_name": "娱乐天地"},
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
    rid = str(item.get("profileRoom") or item.get("uid") or "").strip()
    if not rid:
        return None
    title = (item.get("introduction") or item.get("roomName") or item.get("nick") or "").strip()
    if not title:
        title = item.get("nick") or rid
    pic = item.get("screenshot") or item.get("avatar180") or ""
    if pic.startswith("//"):
        pic = "https:" + pic
    online = _fmt_online(item.get("totalCount") or item.get("aliveNum") or 0)
    game = item.get("gameFullName") or ""
    remark = "%s · %s" % (game, online) if game else online
    return {
        "vod_id": rid,
        "vod_name": title,
        "vod_pic": pic,
        "vod_remarks": remark,
    }


async def home(params, context):
    try:
        data = await _get_json(
            HOST + "/cache.php?m=LiveList&do=getLiveListByPage&tagAll=0&page=1"
        )
        datas = (data.get("data") or {}).get("datas") or []
        cards = []
        for it in datas[:48]:
            # 只保留有人气的在线房间
            if int(it.get("totalCount") or 0) <= 0:
                continue
            card = _room_item(it)
            if card:
                cards.append(card)
        await OmniBox.log("info", "[虎牙][home] list=%s" % len(cards))
        return {"class": CLASSES, "list": cards}
    except Exception as e:
        await OmniBox.log("error", "[虎牙][home] %s" % e)
        return {"class": CLASSES, "list": []}


async def category(params, context):
    tid = str(params.get("categoryId") or params.get("type_id") or params.get("tid") or "0")
    page = _page(params.get("page") or params.get("pg") or 1)
    try:
        if tid == "0":
            url = HOST + "/cache.php?m=LiveList&do=getLiveListByPage&tagAll=0&page=%s" % page
        else:
            url = (
                HOST
                + "/cache.php?m=LiveList&do=getLiveListByPage&gameId=%s&tagAll=0&page=%s"
                % (tid, page)
            )
        data = await _get_json(url)
        d = data.get("data") or {}
        datas = d.get("datas") or []
        cards = []
        for it in datas:
            if int(it.get("totalCount") or 0) <= 0:
                continue
            card = _room_item(it)
            if card:
                cards.append(card)
        total_page = int(d.get("totalPage") or page)
        await OmniBox.log(
            "info", "[虎牙][category] tid=%s page=%s list=%s" % (tid, page, len(cards))
        )
        return {
            "list": cards,
            "page": page,
            "pagecount": max(total_page, page),
            "total": int(d.get("totalCount") or 0) or len(cards) * total_page,
        }
    except Exception as e:
        await OmniBox.log("error", "[虎牙][category] %s" % e)
        return {"list": [], "page": page, "pagecount": page, "total": 0}


async def search(params, context):
    keyword = str(params.get("keyword") or params.get("wd") or params.get("key") or "").strip()
    page = _page(params.get("page") or params.get("pg") or 1)
    if not keyword:
        return {"list": [], "page": page, "pagecount": page, "total": 0}
    try:
        url = (
            HOST
            + "/cache.php?m=LiveList&do=getLiveListByPage&search=%s&page=%s"
            % (quote(keyword), page)
        )
        data = await _get_json(url)
        d = data.get("data") or {}
        datas = d.get("datas") or []
        cards = []
        for it in datas:
            if int(it.get("totalCount") or 0) <= 0:
                continue
            card = _room_item(it)
            if card:
                cards.append(card)
        total_page = int(d.get("totalPage") or page)
        await OmniBox.log("info", "[虎牙][search] key=%s list=%s" % (keyword, len(cards)))
        return {
            "list": cards,
            "page": page,
            "pagecount": max(total_page, page),
            "total": int(d.get("totalCount") or 0) or len(cards),
        }
    except Exception as e:
        await OmniBox.log("error", "[虎牙][search] %s" % e)
        return {"list": [], "page": page, "pagecount": page, "total": 0}


async def detail(params, context):
    rid = str(params.get("vodId") or params.get("id") or params.get("ids") or "").strip()
    if not rid:
        return {"list": []}
    try:
        # 房间 profile
        url = "https://mp.huya.com/cache.php?m=Live&do=profileRoom&roomid=%s" % rid
        data = await _get_json(url, referer=HOST + "/" + rid)
        info = (data.get("data") or {}).get("liveData") or data.get("data") or {}
        if not info:
            # 兜底用列表接口反查
            return {
                "list": [
                    {
                        "vod_id": rid,
                        "vod_name": "虎牙直播间 %s" % rid,
                        "vod_pic": "",
                        "vod_remarks": "在线",
                        "vod_content": "",
                        "vod_play_sources": [
                            {"name": "虎牙", "episodes": [{"name": "直播", "playId": rid}]}
                        ],
                    }
                ]
            }
        title = (
            info.get("introduction")
            or info.get("roomName")
            or info.get("nick")
            or ("虎牙 " + rid)
        )
        pic = info.get("screenshot") or info.get("avatarUrl") or ""
        if pic.startswith("//"):
            pic = "https:" + pic
        online = _fmt_online(info.get("totalCount") or info.get("online") or 0)
        game = info.get("gameFullName") or info.get("gameName") or ""
        owner = info.get("nick") or info.get("ownerName") or ""
        content = "主播: %s\n分区: %s\n人气: %s" % (owner, game, online)
        # 仅在线才返回播放源
        is_live = str(info.get("liveStatus") or info.get("status") or "ON").upper() in (
            "ON",
            "1",
            "LIVE",
            "2",
        ) or int(info.get("totalCount") or 0) > 0
        episodes = [{"name": "直播中", "playId": rid}] if is_live else []
        await OmniBox.log("info", "[虎牙][detail] rid=%s live=%s" % (rid, is_live))
        return {
            "list": [
                {
                    "vod_id": rid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "%s · %s" % (game, online),
                    "vod_content": content,
                    "vod_play_sources": [{"name": "虎牙直播", "episodes": episodes}],
                }
            ]
        }
    except Exception as e:
        await OmniBox.log("error", "[虎牙][detail] %s" % e)
        return {"list": []}


async def play(params, context):
    rid = str(params.get("playId") or params.get("id") or "").strip()
    if not rid:
        return {"urls": [], "parse": 0, "header": {}}
    headers = {"User-Agent": UA, "Referer": HOST + "/" + rid}
    try:
        # 尝试从 profile 拿流
        url = "https://mp.huya.com/cache.php?m=Live&do=profileRoom&roomid=%s" % rid
        data = await _get_json(url, referer=HOST + "/" + rid)
        live_status = (data.get("data") or {}).get("liveStatus")
        if live_status and str(live_status).upper() not in ("ON", "1", "LIVE"):
            await OmniBox.log("info", "[虎牙][play] offline rid=%s" % rid)
            return {"urls": [], "parse": 0, "header": headers}

        stream = (data.get("data") or {}).get("stream") or {}
        # 优先 flv / hls
        base_list = stream.get("baseSteamInfoList") or stream.get("data") or []
        if isinstance(base_list, dict):
            base_list = [base_list]
        play_urls = []
        for s in base_list:
            if not isinstance(s, dict):
                continue
            flv = s.get("sFlvUrl") or s.get("flvUrl")
            flv_name = s.get("sStreamName") or s.get("streamName") or ""
            flv_suffix = s.get("sFlvUrlSuffix") or "flv"
            anti = s.get("sFlvAntiCode") or s.get("antiCode") or ""
            if flv and flv_name:
                full = "%s/%s.%s?%s" % (flv.rstrip("/"), flv_name, flv_suffix, anti)
                play_urls.append({"name": s.get("sCdnType") or "FLV", "url": full})
            hls = s.get("sHlsUrl") or s.get("hlsUrl")
            hls_name = s.get("sStreamName") or flv_name
            hls_suffix = s.get("sHlsUrlSuffix") or "m3u8"
            hls_anti = s.get("sHlsAntiCode") or anti
            if hls and hls_name:
                full = "%s/%s.%s?%s" % (hls.rstrip("/"), hls_name, hls_suffix, hls_anti)
                play_urls.append({"name": (s.get("sCdnType") or "HLS") + "-HLS", "url": full})

        if play_urls:
            await OmniBox.log("info", "[虎牙][play] streams=%s" % len(play_urls))
            return {"urls": play_urls[:6], "parse": 0, "header": headers}

        # 兜底：打开网页解析
        return {
            "urls": [{"name": "网页", "url": HOST + "/" + rid}],
            "parse": 1,
            "header": headers,
        }
    except Exception as e:
        await OmniBox.log("error", "[虎牙][play] %s" % e)
        return {
            "urls": [{"name": "网页", "url": HOST + "/" + rid}],
            "parse": 1,
            "header": headers,
        }


run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
