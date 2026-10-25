# -*- coding: utf-8 -*-
# @name YY直播
# @version 1.0.0
# @description YY直播 OmniBox 源：仅展示在线直播间 / 分类 / 搜索 / 播放
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%9B%B4%E6%92%AD%E5%B9%B3%E5%8F%B0/YY.py
import re
from urllib.parse import quote

from spider_runner import OmniBox, run

HOST = "https://www.yy.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# YY 常用业务/分类（biz 或 index）
CLASSES = [
    {"type_id": "idx", "type_name": "首页热门"},
    {"type_id": "game", "type_name": "游戏"},
    {"type_id": "show", "type_name": "娱乐"},
    {"type_id": "music", "type_name": "音乐"},
    {"type_id": "outdoor", "type_name": "户外"},
    {"type_id": "chat", "type_name": "交友"},
]


def _page(v):
    try:
        return max(1, int(v))
    except (ValueError, TypeError):
        return 1


async def _get(url, referer=HOST + "/", is_json=True):
    res = await OmniBox.request(
        url,
        {
            "method": "GET",
            "headers": {
                "User-Agent": UA,
                "Referer": referer,
                "Accept": "application/json, text/html, */*",
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
    if not is_json:
        return text
    # 有时带 callback
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    m = re.search(r"^[a-zA-Z_]+\((.*)\);?$", text, re.S)
    if m:
        text = m.group(1)
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
    # 兼容多种字段名
    rid = str(
        item.get("sid")
        or item.get("roomId")
        or item.get("liveId")
        or item.get("uid")
        or item.get("id")
        or ""
    ).strip()
    if not rid:
        return None
    title = (
        item.get("desc")
        or item.get("liveDesc")
        or item.get("name")
        or item.get("nick")
        or item.get("anchorName")
        or ""
    ).strip()
    if not title:
        title = item.get("nick") or rid
    pic = (
        item.get("thumb")
        or item.get("cover")
        or item.get("screenshot")
        or item.get("avatar")
        or item.get("img")
        or ""
    )
    if pic.startswith("//"):
        pic = "https:" + pic
    online = _fmt_online(
        item.get("users") or item.get("online") or item.get("viewers") or item.get("num") or 0
    )
    game = item.get("biz") or item.get("gameName") or item.get("tag") or ""
    remark = "%s · %s" % (game, online) if game else online
    return {
        "vod_id": rid,
        "vod_name": title,
        "vod_pic": pic,
        "vod_remarks": remark,
    }


async def home(params, context):
    try:
        # YY 首页推荐
        url = "https://www.yy.com/api/index/recommend/live?page=1&pageSize=40"
        data = await _get(url)
        lst = data.get("data") or data.get("list") or data.get("lives") or []
        if isinstance(lst, dict):
            lst = lst.get("list") or lst.get("data") or []
        cards = []
        for it in lst[:48]:
            card = _room_item(it if isinstance(it, dict) else {})
            if card:
                cards.append(card)
        # 若接口变动，兜底抓页面
        if not cards:
            html = await _get(HOST + "/", is_json=False)
            for m in re.finditer(
                r'href=["\']/(\d+)["\'][^>]*>.*?(?:data-src|src)=["\']([^"\']+)["\']',
                html,
                re.I | re.S,
            ):
                rid, pic = m.group(1), m.group(2)
                if pic.startswith("//"):
                    pic = "https:" + pic
                cards.append(
                    {
                        "vod_id": rid,
                        "vod_name": "YY直播间 " + rid,
                        "vod_pic": pic,
                        "vod_remarks": "在线",
                    }
                )
                if len(cards) >= 40:
                    break
        await OmniBox.log("info", "[YY][home] list=%s" % len(cards))
        return {"class": CLASSES, "list": cards}
    except Exception as e:
        await OmniBox.log("error", "[YY][home] %s" % e)
        return {"class": CLASSES, "list": []}


async def category(params, context):
    tid = str(params.get("categoryId") or params.get("type_id") or params.get("tid") or "idx")
    page = _page(params.get("page") or params.get("pg") or 1)
    try:
        if tid == "idx":
            url = "https://www.yy.com/api/index/recommend/live?page=%s&pageSize=40" % page
        else:
            # 尝试业务分类接口
            url = (
                "https://www.yy.com/api/live/list?biz=%s&page=%s&pageSize=40"
                % (quote(tid), page)
            )
        data = await _get(url)
        lst = data.get("data") or data.get("list") or data.get("lives") or []
        if isinstance(lst, dict):
            lst = lst.get("list") or lst.get("data") or []
        cards = []
        for it in lst:
            card = _room_item(it if isinstance(it, dict) else {})
            if card:
                cards.append(card)
        await OmniBox.log(
            "info", "[YY][category] tid=%s page=%s list=%s" % (tid, page, len(cards))
        )
        return {
            "list": cards,
            "page": page,
            "pagecount": page + (1 if len(cards) >= 20 else 0),
            "total": len(cards) * page,
        }
    except Exception as e:
        await OmniBox.log("error", "[YY][category] %s" % e)
        return {"list": [], "page": page, "pagecount": page, "total": 0}


async def search(params, context):
    keyword = str(params.get("keyword") or params.get("wd") or params.get("key") or "").strip()
    page = _page(params.get("page") or params.get("pg") or 1)
    if not keyword:
        return {"list": [], "page": page, "pagecount": page, "total": 0}
    try:
        url = (
            "https://www.yy.com/api/search/live?keyword=%s&page=%s&pageSize=20"
            % (quote(keyword), page)
        )
        data = await _get(url)
        lst = data.get("data") or data.get("list") or data.get("lives") or []
        if isinstance(lst, dict):
            lst = lst.get("list") or lst.get("data") or []
        cards = []
        for it in lst:
            card = _room_item(it if isinstance(it, dict) else {})
            if card:
                cards.append(card)
        await OmniBox.log("info", "[YY][search] key=%s list=%s" % (keyword, len(cards)))
        return {
            "list": cards,
            "page": page,
            "pagecount": page + (1 if len(cards) >= 15 else 0),
            "total": len(cards),
        }
    except Exception as e:
        await OmniBox.log("error", "[YY][search] %s" % e)
        return {"list": [], "page": page, "pagecount": page, "total": 0}


async def detail(params, context):
    rid = str(params.get("vodId") or params.get("id") or params.get("ids") or "").strip()
    if not rid:
        return {"list": []}
    try:
        # 尝试获取房间信息
        url = "https://www.yy.com/api/liveInfo?sid=%s" % rid
        data = await _get(url, referer=HOST + "/" + rid)
        info = data.get("data") or data or {}
        if not info or not isinstance(info, dict):
            info = {}
        title = (
            info.get("desc")
            or info.get("liveDesc")
            or info.get("name")
            or ("YY直播间 " + rid)
        )
        pic = info.get("thumb") or info.get("cover") or info.get("screenshot") or ""
        if pic.startswith("//"):
            pic = "https:" + pic
        online = _fmt_online(info.get("users") or info.get("online") or 0)
        owner = info.get("nick") or info.get("anchorName") or info.get("name") or ""
        is_live = bool(info.get("liveStatus") in (1, "1", True, "ON", "live") or int(info.get("users") or 0) > 0)
        # 也可用 hls 接口探测
        if not is_live:
            try:
                probe = await _get(
                    "https://interface.yy.com/hls/new/get/%s/%s/1200?source=wapyy&callback="
                    % (rid, rid),
                    referer="https://wap.yy.com/mobileweb/%s" % rid,
                )
                if probe.get("hls") or probe.get("video"):
                    is_live = True
            except Exception:
                pass
        content = "主播: %s\n人气: %s" % (owner, online)
        episodes = [{"name": "直播中", "playId": rid}] if is_live else []
        await OmniBox.log("info", "[YY][detail] rid=%s live=%s" % (rid, is_live))
        return {
            "list": [
                {
                    "vod_id": rid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": online or ("直播中" if is_live else "未开播"),
                    "vod_content": content,
                    "vod_play_sources": [{"name": "YY直播", "episodes": episodes}],
                }
            ]
        }
    except Exception as e:
        await OmniBox.log("error", "[YY][detail] %s" % e)
        return {"list": []}


async def play(params, context):
    rid = str(params.get("playId") or params.get("id") or "").strip()
    if not rid:
        return {"urls": [], "parse": 0, "header": {}}
    headers = {
        "User-Agent": UA,
        "Referer": "https://wap.yy.com/mobileweb/%s" % rid,
    }
    try:
        # real-url 风格取流
        room_url = (
            "https://interface.yy.com/hls/new/get/%s/%s/1200?source=wapyy&callback="
            % (rid, rid)
        )
        data = await _get(room_url, referer=headers["Referer"])
        if not data.get("hls") and not data.get("video"):
            await OmniBox.log("info", "[YY][play] offline rid=%s" % rid)
            return {"urls": [], "parse": 0, "header": headers}

        xa = data.get("audio") or ""
        xv = data.get("video") or ""
        if xv:
            xv = re.sub(r"_0_\d+_0", "_0_0_0", xv)
            stream_url = (
                "https://interface.yy.com/hls/get/stream/15013/%s/15013/%s?source=h5player&type=m3u8"
                % (xv, xa or "0")
            )
            sdata = await _get(stream_url, referer=headers["Referer"])
            real = sdata.get("hls") or sdata.get("url")
            if real:
                await OmniBox.log("info", "[YY][play] got m3u8")
                return {
                    "urls": [{"name": "原画", "url": real}],
                    "parse": 0,
                    "header": headers,
                }

        # 兜底网页
        return {
            "urls": [{"name": "网页", "url": HOST + "/" + rid}],
            "parse": 1,
            "header": {"User-Agent": UA, "Referer": HOST + "/"},
        }
    except Exception as e:
        await OmniBox.log("error", "[YY][play] %s" % e)
        return {
            "urls": [{"name": "网页", "url": HOST + "/" + rid}],
            "parse": 1,
            "header": {"User-Agent": UA, "Referer": HOST + "/"},
        }


run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
