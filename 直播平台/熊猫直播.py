# -*- coding: utf-8 -*-
# @name 熊猫直播
# @version 1.2.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%9B%B4%E6%92%AD%E5%B9%B3%E5%8F%B0/熊猫直播.py
# @description PandaLive 直播源（OmniBox）：仅展示在线直播间；play 用 action=watch&userId 取 PlayList.hls

"""
熊猫直播 (PandaLive) — OmniBox v1.2.0

站点: https://www.pandalive.co.kr
列表: POST /v1/live
播放: POST /v1/live/play  (form: action=watch&userId=...)
说明: 仅返回在线房间；密码房 / 未开播跳过；成人房需地区可用；播放需 Origin 头
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


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


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
            f"{API}/v1/member/app_token",
            {"method": "GET", "headers": _headers(), "timeout": 8},
        )
    except Exception:
        pass
    _token_ready = True


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
            f"{API}/v1/live",
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
        j = json.loads(text) if text.strip().startswith("{") else {}
        if isinstance(j, dict) and isinstance(j.get("list"), list):
            return j
    except Exception as e:
        await OmniBox.log("warn", "[list] %s" % e)
    return {"list": []}


async def _list_aggregate(max_pages=4, page_size=40, order_by="user", only_new="N"):
    cache_key = "pandalive_agg_v3_%s_%s" % (order_by, only_new)
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
            if not isinstance(it, dict):
                continue
            # 仅保留在线：跳过密码房、未开播、无 userId
            if it.get("isPw"):
                continue
            if not _is_online(it):
                continue
            uid = str(it.get("userId") or "").strip()
            code = str(it.get("code") or uid).strip()
            key = uid or code
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(it)
            added += 1
        if added == 0 and p > 1:
            break

    try:
        await OmniBox.setCache(
            cache_key, {"expiresAt": int(time.time()) + 25, "list": result}
        )
    except Exception:
        pass
    return result


def _extract_m3u8(obj):
    """从 PlayList.hls / hls2 / hls3 或全文正则提取 m3u8。"""
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
    # media 内偶发直链
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
    """优先 form: action=watch&userId=；失败再试 JSON play_id。"""
    await _ensure_token()
    uid = (user_id or "").strip()
    code = (play_code or "").strip()
    if not uid and code:
        uid = code.split("_")[0]

    # 1) 官方主流：form-urlencoded
    form = "action=watch&userId=%s&password=&shareLinkType=" % quote(uid)
    headers = _headers(
        {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": "%s/play/%s" % (BASE, quote(uid)),
        }
    )
    try:
        res = await OmniBox.request(
            f"{API}/v1/live/play",
            {"method": "POST", "headers": headers, "body": form, "timeout": 12},
        )
        text = res.get("body") or ""
        if text.strip().startswith("{"):
            j = json.loads(text)
            if _extract_m3u8(j) or j.get("result") is True:
                return j
            # 记录错误便于排查
            err = j.get("message") or (j.get("errorData") or {}).get("code") or ""
            if err:
                await OmniBox.log("warn", "[play] watch 返回: %s" % str(err)[:120])
    except Exception as e:
        await OmniBox.log("warn", "[play] watch 失败: %s" % e)

    # 2) 兼容旧 JSON body（部分端）
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
                f"{API}/v1/live/play",
                {"method": "POST", "headers": headers2, "body": body, "timeout": 12},
            )
            text = res.get("body") or ""
            if text.strip().startswith("{"):
                return json.loads(text)
        except Exception as e:
            await OmniBox.log("warn", "[play] json 失败: %s" % e)

    return {}


def _is_online(it):
    """严格判断是否在播：isLive 为真，或有观众数且未标记下播。"""
    if not isinstance(it, dict):
        return False
    if it.get("isPw"):
        return False
    live = it.get("isLive")
    if live is False or live in (0, "0", "N", "n", "false", "False", "OFF", "off"):
        return False
    if live is True or live in (1, "1", "Y", "y", "true", "True", "ON", "on"):
        return True
    # 字段缺失时：有观众/热度且非空 userId 才当在线
    uid = str(it.get("userId") or "").strip()
    if not uid:
        return False
    viewers = _to_int(it.get("user") or it.get("viewer") or 0)
    return viewers > 0


def _to_vod(it):
    if not _is_online(it):
        return None
    title = str(it.get("title") or it.get("userNick") or it.get("userId") or "LIVE").strip()
    pic = str(it.get("thumbUrl") or it.get("ivsThumbnail") or it.get("userImg") or "")
    user_id = str(it.get("userId") or "").strip()
    play_code = str(it.get("code") or user_id).strip()
    # vod_id: userId|code  （播放优先用 userId）
    vod_id = "%s|%s" % (user_id, play_code)
    viewers = it.get("user") or 0
    likes = it.get("likeCnt") or 0
    adult = "🔞" if it.get("isAdult") else ""
    remarks = "%s观众%s | 赞%s" % (adult, viewers, likes)
    return {
        "vod_id": vod_id,
        "vod_name": title,
        "vod_pic": pic,
        "vod_remarks": remarks,
    }


def _tid_to_sort(tid):
    t = (tid or "").lower()
    if t in ("live_newbj", "newbj"):
        return "user", "Y"
    if t in ("live_hot", "hot"):
        return "hot", "N"
    if t in ("live_new", "new"):
        return "new", "N"
    return "user", "N"


async def home(params, context):
    try:
        await OmniBox.log("info", "[home] from=%s" % (context or {}).get("from", "web"))
        classes = [
            {"type_name": "人气", "type_id": "live"},
            {"type_name": "热门", "type_id": "live_hot"},
            {"type_name": "新秀", "type_id": "live_newbj"},
            {"type_name": "最新", "type_id": "live_new"},
        ]
        items = await _list_aggregate(max_pages=2, page_size=40, order_by="user", only_new="N")
        videos = [v for v in (_to_vod(it) for it in items[:60]) if v]
        return {"class": classes, "list": videos[:48], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[home] 失败: %s" % e)
        return {"class": [], "list": [], "filters": {}}


async def category(params, context):
    try:
        tid = str((params or {}).get("categoryId") or "live")
        page = _to_int((params or {}).get("page"), 1) or 1
        order_by, only_new = _tid_to_sort(tid)
        await OmniBox.log("info", "[category] %s page=%s" % (tid, page))
        if page == 1:
            items = await _list_aggregate(
                max_pages=3, page_size=40, order_by=order_by, only_new=only_new
            )
        else:
            j = await _list_live(page=page, page_size=40, order_by=order_by, only_new=only_new)
            items = [
                it
                for it in (j.get("list") or [])
                if isinstance(it, dict) and _is_online(it)
            ]
        videos = [v for v in (_to_vod(it) for it in items) if v]
        pagecount = page + 1 if len(videos) >= 20 else page
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 40,
            "total": pagecount * 40,
        }
    except Exception as e:
        await OmniBox.log("error", "[category] 失败: %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 40}


async def detail(params, context):
    try:
        vid = str((params or {}).get("videoId") or "").strip()
        if not vid:
            return {"list": []}
        await OmniBox.log("info", "[detail] %s" % vid)
        parts = vid.split("|")
        user_id = parts[0].strip() if parts else vid
        play_code = parts[1].strip() if len(parts) > 1 else ""
        # 标题可能在第 3 段
        title_hint = parts[2] if len(parts) > 2 else ""

        j = await _live_play(user_id, play_code)
        media = j.get("media") or {}
        title = str(
            media.get("title") or title_hint or media.get("userNick") or user_id
        ).strip()
        nick = str(media.get("userNick") or user_id).strip()
        pic = str(media.get("thumbUrl") or media.get("ivsThumbnail") or "")
        is_live = media.get("isLive")
        is_pw = media.get("isPw")
        # 详情也只在真正在播时给播放源
        online = bool(is_live) and not is_pw
        if is_live is None:
            online = bool(_extract_m3u8(j)) and not is_pw
        remarks = "直播中" if online else ("密码房" if is_pw else "未开播")
        if media.get("isAdult"):
            remarks = "🔞" + remarks

        episodes = []
        if online:
            episodes = [
                {"name": "直播", "playId": "%s|%s" % (user_id, play_code or user_id)}
            ]
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remarks,
            "vod_actor": nick,
            "vod_content": "userId: %s" % user_id,
            "vod_play_sources": [{"name": "PandaLive", "episodes": episodes}] if episodes else [],
        }
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", "[detail] 失败: %s" % e)
        return {"list": []}


async def search(params, context):
    try:
        key = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 0}
        await OmniBox.log("info", "[search] %s" % key)
        items = await _list_aggregate(max_pages=3, page_size=40)
        key_l = key.lower()
        result = []
        for it in items:
            if not _is_online(it):
                continue
            title = str(it.get("title") or "")
            user_id = str(it.get("userId") or "")
            nick = str(it.get("userNick") or "")
            if (
                key_l in title.lower()
                or key_l in user_id.lower()
                or key_l in nick.lower()
            ):
                v = _to_vod(it)
                if v:
                    result.append(v)
        # 精确 userId：仅当当前在播才加入（详情页再校验）
        if not result and re.match(r"^[\w.-]+$", key):
            j = await _live_play(key, key)
            media = (j or {}).get("media") or {}
            if media.get("isLive") and not media.get("isPw"):
                result.append(
                    {
                        "vod_id": "%s|%s" % (key, key),
                        "vod_name": str(media.get("title") or media.get("userNick") or key),
                        "vod_pic": str(media.get("thumbUrl") or ""),
                        "vod_remarks": "直播中",
                    }
                )
        return {
            "list": result,
            "page": 1,
            "pagecount": 1,
            "limit": len(result),
            "total": len(result),
        }
    except Exception as e:
        await OmniBox.log("error", "[search] 失败: %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 0}


async def play(params, context):
    try:
        vid = str((params or {}).get("playId") or "").strip()
        flag = str((params or {}).get("flag") or "play")
        if not vid:
            raise ValueError("playId 为空")
        await OmniBox.log("info", "[play] %s" % vid)

        parts = vid.split("|")
        user_id = parts[0].strip() if parts else vid
        play_code = parts[1].strip() if len(parts) > 1 else ""
        if not user_id:
            user_id = (play_code or "").split("_")[0]

        j = await _live_play(user_id, play_code)
        m3u8 = _extract_m3u8(j)

        headers = {
            "User-Agent": UA,
            "Referer": BASE + "/",
            "Origin": BASE,
        }

        if m3u8:
            return {
                "urls": [{"name": "直播", "url": m3u8}],
                "flag": flag,
                "header": headers,
                "parse": 0,
            }

        # 失败原因
        err = ""
        if isinstance(j, dict):
            err = str(
                j.get("message")
                or (j.get("errorData") or {}).get("code")
                or j.get("msg")
                or ""
            )
        await OmniBox.log("warn", "[play] 无 m3u8 user=%s err=%s" % (user_id, err[:80]))

        # 回退网页（壳子可再解析）
        fallback = "%s/play/%s" % (BASE, quote(user_id))
        return {
            "urls": [{"name": "直播", "url": fallback}],
            "flag": flag,
            "header": headers,
            "parse": 1,
        }
    except Exception as e:
        await OmniBox.log("error", "[play] 失败: %s" % e)
        return {
            "urls": [],
            "flag": (params or {}).get("flag", "play"),
            "header": {},
            "parse": 0,
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
