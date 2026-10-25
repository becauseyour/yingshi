# -*- coding: utf-8 -*-
# @name YY直播
# @version 1.1.0
# @description YY直播 OmniBox 源：仅展示在线直播间（首页/WAP 解析 + HLS 取流）
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%9B%B4%E6%92%AD%E5%B9%B3%E5%8F%B0/YY.py
import json
import re
from urllib.parse import quote

from spider_runner import OmniBox, run

HOST = "https://www.yy.com"
WAP = "https://wap.yy.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# YY 常用业务/分类（接口多已失效，统一走首页热门在线列表）
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
    if not is_json:
        return text
    if status and (status < 200 or status >= 400):
        return {}
    text = text.strip()
    if not text or text[:1] in ("<",):
        return {}
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    m = re.search(r"^[a-zA-Z_]+\((.*)\);?$", text, re.S)
    if m:
        text = m.group(1)
    try:
        return json.loads(text) if text else {}
    except Exception:
        return {}


def _parse_rooms_from_html(html):
    """从首页/WAP HTML 提取在线房间（data-sid / 路径数字）。"""
    if not html:
        return []
    cards = []
    seen = set()

    # data-sid="123" 附近取封面/标题
    for m in re.finditer(
        r'data-sid=["\'](\d{5,})["\']([^>]*>)([\s\S]{0,400})',
        html,
        re.I,
    ):
        rid = m.group(1)
        if rid in seen:
            continue
        chunk = m.group(0) + (m.group(3) or "")
        pic = ""
        pm = re.search(
            r'(?:data-src|data-original|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
            chunk,
            re.I,
        )
        if pm:
            pic = pm.group(1)
            if pic.startswith("//"):
                pic = "https:" + pic
        title = ""
        tm = re.search(r'(?:title|alt)=["\']([^"\']{2,80})["\']', chunk, re.I)
        if tm:
            title = tm.group(1).strip()
        if not title:
            title = "YY直播间 " + rid
        seen.add(rid)
        cards.append(
            {
                "vod_id": rid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "直播中",
            }
        )

    # 补充：纯 sid 出现（WAP）
    if len(cards) < 8:
        for rid in re.findall(r'(?:data-sid=["\']|/mobileweb/)(\d{5,})', html, re.I):
            if rid in seen:
                continue
            seen.add(rid)
            cards.append(
                {
                    "vod_id": rid,
                    "vod_name": "YY直播间 " + rid,
                    "vod_pic": "",
                    "vod_remarks": "直播中",
                }
            )
            if len(cards) >= 40:
                break
    return cards[:48]


async def _list_online():
    """聚合 PC 首页 + WAP，只返回解析到的在线房间。"""
    cards = []
    for url in (HOST + "/", WAP + "/", WAP + "/mobileweb/"):
        try:
            html = await _get(url, referer=HOST + "/", is_json=False)
            part = _parse_rooms_from_html(html)
            for c in part:
                if not any(x["vod_id"] == c["vod_id"] for x in cards):
                    cards.append(c)
            if len(cards) >= 30:
                break
        except Exception:
            continue
    return cards


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
        cards = await _list_online()
        await OmniBox.log("info", "[YY][home] list=%s" % len(cards))
        return {"class": CLASSES, "list": cards}
    except Exception as e:
        await OmniBox.log("error", "[YY][home] %s" % e)
        return {"class": CLASSES, "list": []}


async def category(params, context):
    tid = str(params.get("categoryId") or params.get("type_id") or params.get("tid") or "idx")
    page = _page(params.get("page") or params.get("pg") or 1)
    try:
        # 官方分类 API 多已 404，统一返回在线热门；分页做切片
        cards = await _list_online()
        page_size = 20
        start = (page - 1) * page_size
        chunk = cards[start : start + page_size]
        pagecount = max(1, (len(cards) + page_size - 1) // page_size)
        await OmniBox.log(
            "info", "[YY][category] tid=%s page=%s list=%s" % (tid, page, len(chunk))
        )
        return {
            "list": chunk,
            "page": page,
            "pagecount": pagecount,
            "total": len(cards),
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
        cards = []
        # 数字关键字当作房间号直达（再确认是否可播）
        if re.match(r"^\d{5,}$", keyword):
            cards.append(
                {
                    "vod_id": keyword,
                    "vod_name": "YY直播间 " + keyword,
                    "vod_pic": "",
                    "vod_remarks": "直达",
                }
            )
        # 本地过滤在线列表
        online = await _list_online()
        key_l = keyword.lower()
        for c in online:
            if key_l in (c.get("vod_name") or "").lower() or key_l in (c.get("vod_id") or ""):
                if not any(x["vod_id"] == c["vod_id"] for x in cards):
                    cards.append(c)
        await OmniBox.log("info", "[YY][search] key=%s list=%s" % (keyword, len(cards)))
        return {
            "list": cards,
            "page": page,
            "pagecount": 1,
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
        # 也可用 hls 接口探测（hls=404 视为未开播）
        if not is_live:
            try:
                probe = await _get(
                    "https://interface.yy.com/hls/new/get/%s/%s/1200?source=wapyy&callback="
                    % (rid, rid),
                    referer="https://wap.yy.com/mobileweb/%s" % rid,
                )
                hls = str(probe.get("hls") or "")
                video = str(probe.get("video") or "")
                if (video or hls) and hls not in ("404", "0", "null"):
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
        hls0 = str(data.get("hls") or "")
        if (not data.get("video") and not data.get("hls")) or hls0 in ("404", "0"):
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
