# -*- coding: utf-8 -*-
# @name 熊猫直播
# @version 1.3.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%9B%B4%E6%92%AD%E5%B9%B3%E5%8F%B0/熊猫直播.py
# @description PandaLive 官方源：按分类只显示在线直播间（人气/热门/新秀/免费/粉丝/成人）

"""
熊猫直播 (PandaLive) — OmniBox v1.3.0

站点: https://www.pandalive.co.kr
列表: POST /v1/live  （仅 isLive 在线，跳过密码房）
播放: POST /v1/live/play  (action=watch&userId=...)
分类: 人气 / 热门 / 新秀 / 免费 / 粉丝 / 成人
说明: 成人分类依赖接口返回 isAdult；部分地区未登录可能为空
"""

import json
import re
import time
from urllib.parse import quote

from spider_runner import OmniBox, run

BASE = "https://www.pandalive.co.kr"
API = "https://api.pandalive.co.kr"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)

_x_device_info = {"t": "webPc", "v": "1.0", "ui": 0}
_token_ready = False

CLASSES = [
    {"type_id": "user", "type_name": "人气"},
    {"type_id": "hot", "type_name": "热门"},
    {"type_id": "new", "type_name": "新秀"},
    {"type_id": "free", "type_name": "免费"},
    {"type_id": "fan", "type_name": "粉丝"},
    {"type_id": "adult", "type_name": "成人"},
]


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _page(v):
    try:
        return max(1, int(v))
    except (ValueError, TypeError):
        return 1


def _headers(extra=None):
    h = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Origin": BASE,
        "Referer": BASE + "/",
        "x-device-info": json.dumps(_x_device_info, separators=(",", ":")),
    }
    if extra:
        h.update(extra)
    return h


async def _ensure_token():
    global _token_ready
    if _token_ready:
        return
    try:
        await OmniBox.request(BASE, {"method": "GET", "headers": _headers(), "timeout": 8})
    except Exception:
        pass
    try:
        await OmniBox.request(
            "%s/v1/member/app_token" % API,
            {"method": "GET", "headers": _headers(), "timeout": 8},
        )
    except Exception:
        pass
    _token_ready = True


def _is_online(it):
    if not isinstance(it, dict):
        return False
    if it.get("isPw"):
        return False
    live = it.get("isLive")
    if live is False or live in (0, "0", "N", "n", "false", "False", "OFF", "off"):
        return False
    if live is True or live in (1, "1", "Y", "y", "true", "True", "ON", "on"):
        return True
    uid = str(it.get("userId") or "").strip()
    if not uid:
        return False
    return _to_int(it.get("user") or it.get("viewer") or 0) > 0


def _room_type(it):
    return str(it.get("type") or it.get("liveType") or "").lower()


def _match_category(it, tid):
    """在已在线前提下按分类过滤。"""
    if tid in ("user", "hot", "new", "live", ""):
        return True
    if tid == "free":
        return _room_type(it) in ("free", "", "live") and not it.get("isAdult")
    if tid == "fan":
        return _room_type(it) in ("fan", "fans", "fanclub") or str(it.get("listUp") or "") == "fan"
    if tid == "adult":
        return bool(it.get("isAdult"))
    return True


def _order_for_tid(tid):
    if tid == "hot":
        return "hot", "N"
    if tid == "new":
        return "new", "Y"
    # free/fan/adult 也按人气拉，再本地滤
    return "user", "N"


async def _list_live(page=1, page_size=40, order_by="user", only_new="N"):
    await _ensure_token()
    offset = max(0, (page - 1) * page_size)
    body = "orderBy=%s&onlyNewBj=%s&limit=%s&offset=%s" % (
        quote(str(order_by)),
        only_new,
        page_size,
        offset,
    )
    try:
        res = await OmniBox.request(
            "%s/v1/live" % API,
            {
                "method": "POST",
                "headers": _headers(
                    {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
                ),
                "body": body,
                "timeout": 10,
            },
        )
        text = res.get("body") or ""
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="ignore")
        j = json.loads(text) if str(text).strip().startswith("{") else {}
        if isinstance(j, dict) and isinstance(j.get("list"), list):
            return j
    except Exception as e:
        await OmniBox.log("warn", "[list] %s" % e)
    return {"list": []}


async def _collect_online(tid="user", max_pages=5, page_size=40):
    """拉取多页并只保留在线 + 符合分类的房间。"""
    order_by, only_new = _order_for_tid(tid)
    cache_key = "pandalive_cat_v13_%s_%s_%s" % (tid, order_by, only_new)
    try:
        cached = await OmniBox.getCache(cache_key)
        if isinstance(cached, dict) and isinstance(cached.get("list"), list) and cached["list"]:
            return cached["list"]
    except Exception:
        pass

    seen, result = set(), []
    for p in range(1, max_pages + 1):
        j = await _list_live(page=p, page_size=page_size, order_by=order_by, only_new=only_new)
        items = j.get("list") or []
        added = 0
        for it in items:
            if not isinstance(it, dict) or not _is_online(it):
                continue
            if not _match_category(it, tid):
                continue
            uid = str(it.get("userId") or "").strip()
            if not uid or uid in seen:
                continue
            seen.add(uid)
            result.append(it)
            added += 1
        if not items:
            break
        # 成人/粉丝等本地过滤类：继续翻页凑数量
        if tid in ("adult", "fan", "free") and len(result) < 30 and p < max_pages:
            continue
        if added == 0 and p > 1 and tid not in ("adult", "fan", "free"):
            break

    try:
        await OmniBox.setCache(
            cache_key, {"expiresAt": int(time.time()) + 20, "list": result}
        )
    except Exception:
        pass
    return result


def _to_vod(it):
    if not _is_online(it):
        return None
    title = str(it.get("title") or it.get("userNick") or it.get("userId") or "LIVE").strip()
    nick = str(it.get("userNick") or it.get("userId") or "").strip()
    pic = str(it.get("thumbUrl") or it.get("ivsThumbnail") or it.get("userImg") or "")
    user_id = str(it.get("userId") or "").strip()
    play_code = str(it.get("code") or user_id).strip()
    vod_id = "%s|%s" % (user_id, play_code)
    viewers = _to_int(it.get("user") or 0)
    if viewers >= 10000:
        online = "%.1f万" % (viewers / 10000.0)
    else:
        online = str(viewers)
    tags = []
    if it.get("isAdult"):
        tags.append("成人")
    rt = _room_type(it)
    if rt and rt not in ("live", "free", ""):
        tags.append(rt)
    elif rt == "free":
        tags.append("免费")
    remark = "观众%s" % online
    if tags:
        remark = "%s · %s" % (remark, " ".join(tags))
    return {
        "vod_id": vod_id,
        "vod_name": nick or title,
        "vod_pic": pic,
        "vod_remarks": remark,
    }


def _extract_m3u8(obj):
    if not isinstance(obj, dict):
        return ""
    playlist = obj.get("PlayList") or obj.get("playList") or {}
    if isinstance(playlist, dict):
        for key in ("hls", "hls2", "hls3", "HLS", "HLS2"):
            arr = playlist.get(key)
            if isinstance(arr, list) and arr:
                first = arr[0]
                if isinstance(first, dict) and first.get("url"):
                    return str(first["url"]).strip()
                if isinstance(first, str) and first.startswith("http"):
                    return first.strip()
            if isinstance(arr, dict) and arr.get("url"):
                return str(arr["url"]).strip()
            if isinstance(arr, str) and arr.startswith("http"):
                return arr.strip()
    media = obj.get("media") or {}
    if isinstance(media, dict):
        for k in ("url", "streamUrl", "playUrl"):
            v = media.get(k)
            if isinstance(v, str) and ".m3u8" in v:
                return v.strip()
    try:
        text = json.dumps(obj, ensure_ascii=False)
        m = re.search(r'https?://[^\s"\\]+\.m3u8[^\s"\\]*', text)
        if m:
            return m.group(0).replace("\\u0026", "&").replace("\\/", "/")
    except Exception:
        pass
    return ""


async def _live_play(user_id, play_code=""):
    await _ensure_token()
    uid = (user_id or "").strip()
    code = (play_code or "").strip()
    if not uid and code:
        uid = code.split("_")[0]

    form = "action=watch&userId=%s&password=&shareLinkType=" % quote(uid)
    headers = _headers(
        {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": "%s/play/%s" % (BASE, quote(uid)),
        }
    )
    try:
        res = await OmniBox.request(
            "%s/v1/live/play" % API,
            {"method": "POST", "headers": headers, "body": form, "timeout": 12},
        )
        text = res.get("body") or ""
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="ignore")
        if str(text).strip().startswith("{"):
            j = json.loads(text)
            if _extract_m3u8(j) or j.get("result") is True:
                return j
            err = j.get("message") or (j.get("errorData") or {}).get("code") or ""
            if err:
                await OmniBox.log("warn", "[play] watch 返回: %s" % str(err)[:120])
    except Exception as e:
        await OmniBox.log("warn", "[play] watch 失败: %s" % e)

    if code:
        body = json.dumps({"play_id": code, "device": "webPc", "player": "ivs"})
        headers2 = _headers(
            {
                "Content-Type": "application/json",
                "Referer": "%s/play/%s" % (BASE, quote(uid or code.split("_")[0])),
            }
        )
        try:
            res = await OmniBox.request(
                "%s/v1/live/play" % API,
                {"method": "POST", "headers": headers2, "body": body, "timeout": 12},
            )
            text = res.get("body") or ""
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="ignore")
            if str(text).strip().startswith("{"):
                return json.loads(text)
        except Exception as e:
            await OmniBox.log("warn", "[play] json 失败: %s" % e)
    return {}


async def home(params, context):
    try:
        items = await _collect_online("user", max_pages=3)
        cards = []
        for it in items[:48]:
            v = _to_vod(it)
            if v:
                cards.append(v)
        await OmniBox.log("info", "[熊猫][home] online=%s" % len(cards))
        return {"class": CLASSES, "list": cards, "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[熊猫][home] %s" % e)
        return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    tid = str(
        (params or {}).get("categoryId")
        or (params or {}).get("type_id")
        or (params or {}).get("tid")
        or "user"
    )
    page = _page((params or {}).get("page") or (params or {}).get("pg") or 1)
    try:
        # 本地过滤类：一次多拉再切片；排序类：按页请求
        if tid in ("adult", "fan", "free"):
            all_items = await _collect_online(tid, max_pages=8)
            limit = 40
            start = (page - 1) * limit
            chunk = all_items[start : start + limit]
            pagecount = max(1, (len(all_items) + limit - 1) // limit)
            total = len(all_items)
        else:
            order_by, only_new = _order_for_tid(tid)
            j = await _list_live(page=page, page_size=40, order_by=order_by, only_new=only_new)
            raw = j.get("list") or []
            chunk = [it for it in raw if isinstance(it, dict) and _is_online(it) and _match_category(it, tid)]
            pagecount = page + (1 if len(raw) >= 20 else 0)
            total = pagecount * 40

        cards = []
        for it in chunk:
            v = _to_vod(it)
            if v:
                cards.append(v)
        await OmniBox.log(
            "info", "[熊猫][category] tid=%s page=%s n=%s" % (tid, page, len(cards))
        )
        return {
            "list": cards,
            "page": page,
            "pagecount": pagecount,
            "limit": 40,
            "total": total,
        }
    except Exception as e:
        await OmniBox.log("error", "[熊猫][category] %s" % e)
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
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}
    try:
        key_l = key.lower()
        items = await _collect_online("user", max_pages=5)
        cards = []
        for it in items:
            v = _to_vod(it)
            if not v:
                continue
            if (
                key_l in (v.get("vod_name") or "").lower()
                or key_l in (v.get("vod_id") or "").lower()
                or key_l in str(it.get("title") or "").lower()
                or key_l in str(it.get("userId") or "").lower()
            ):
                cards.append(v)
        # 纯数字/id 直达
        if not cards and re.match(r"^[\w.-]+$", key):
            cards.append(
                {
                    "vod_id": "%s|%s" % (key, key),
                    "vod_name": key,
                    "vod_pic": "",
                    "vod_remarks": "直达",
                }
            )
        return {
            "list": cards[:50],
            "page": page,
            "pagecount": 1,
            "total": len(cards),
        }
    except Exception as e:
        await OmniBox.log("error", "[熊猫][search] %s" % e)
        return {"list": [], "page": page, "pagecount": 0, "total": 0}


async def detail(params, context):
    p = params or {}
    vid = str(
        p.get("videoId") or p.get("vodId") or p.get("id") or p.get("ids") or ""
    ).strip()
    if not vid:
        return {"list": []}
    if "|" in vid:
        user_id, play_code = vid.split("|", 1)
    else:
        user_id, play_code = vid, vid
    user_id = user_id.strip()
    play_code = play_code.strip()
    try:
        title, pic, remarks = user_id, "", "在线"
        # 从缓存列表里补信息
        for tid in ("user", "hot", "new"):
            items = await _collect_online(tid, max_pages=2)
            hit = None
            for it in items:
                if str(it.get("userId") or "") == user_id:
                    hit = it
                    break
            if hit:
                title = str(hit.get("title") or hit.get("userNick") or user_id)
                pic = str(hit.get("thumbUrl") or hit.get("ivsThumbnail") or "")
                v = _to_vod(hit)
                if v:
                    remarks = v.get("vod_remarks") or remarks
                break

        episodes = [{"name": "直播中", "playId": "%s|%s" % (user_id, play_code)}]
        await OmniBox.log("info", "[熊猫][detail] uid=%s" % user_id)
        return {
            "list": [
                {
                    "vod_id": "%s|%s" % (user_id, play_code),
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks,
                    "vod_actor": user_id,
                    "vod_content": "userId: %s" % user_id,
                    "vod_play_sources": [{"name": "熊猫直播", "episodes": episodes}],
                }
            ]
        }
    except Exception as e:
        await OmniBox.log("error", "[熊猫][detail] %s" % e)
        return {
            "list": [
                {
                    "vod_id": user_id,
                    "vod_name": user_id,
                    "vod_play_sources": [
                        {
                            "name": "熊猫直播",
                            "episodes": [{"name": "直播", "playId": "%s|%s" % (user_id, play_code)}],
                        }
                    ],
                }
            ]
        }


async def play(params, context):
    try:
        play_id = str((params or {}).get("playId") or "").strip()
        flag = str((params or {}).get("flag") or "play")
        if not play_id:
            # 兼容 videoId
            play_id = str((params or {}).get("videoId") or (params or {}).get("id") or "").strip()
        if not play_id:
            raise ValueError("playId 为空")

        if "|" in play_id:
            user_id, play_code = play_id.split("|", 1)
        else:
            user_id, play_code = play_id, ""

        j = await _live_play(user_id, play_code)
        m3u8 = _extract_m3u8(j)
        headers = {
            "User-Agent": UA,
            "Origin": BASE,
            "Referer": "%s/play/%s" % (BASE, quote(user_id)),
        }
        if m3u8:
            await OmniBox.log("info", "[熊猫][play] ok uid=%s" % user_id)
            return {
                "urls": [{"name": "直播", "url": m3u8}],
                "flag": flag,
                "header": headers,
                "parse": 0,
                "extra": {"live": True},
            }
        # 取流失败：回落网页
        await OmniBox.log("warn", "[熊猫][play] no m3u8 uid=%s" % user_id)
        return {
            "urls": [{"name": "网页", "url": "%s/play/%s" % (BASE, quote(user_id))}],
            "flag": flag,
            "header": headers,
            "parse": 1,
            "extra": {"live": True},
        }
    except Exception as e:
        await OmniBox.log("error", "[play] 失败: %s" % e)
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
