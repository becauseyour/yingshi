# -*- coding: utf-8 -*-
# @name SOOP直播
# @version 1.1.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%9B%B4%E6%92%AD%E5%B9%B3%E5%8F%B0/SOOP直播.py
# @description SOOP(原 AfreecaTV) 直播源（OmniBox）：仅展示在线直播间；m 端列表 + player_live_api 取 m3u8

"""
SOOP Live — OmniBox v1.1.0
官网: https://www.sooplive.com
列表: https://api.m.sooplive.com/broad/a/list
播放: live.sooplive.com/afreeca/player_live_api.php + broad_stream_assign
vod_id 格式: {user_id}|{broad_no}
说明: 列表/搜索/详情均只保留当前在播房间
"""

import json
from urllib.parse import quote, urlencode

from spider_runner import OmniBox, run

HOST = "https://www.sooplive.com"
API_LIST = "https://api.m.sooplive.com/broad/a/list"
PLAYER_API = "https://live.sooplive.com/afreeca/player_live_api.php"
STREAM_MGR = "https://livestream-manager.sooplive.com"
PLAY_HOST = "https://play.sooplive.com"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

# 简单分类（接口分页/分类参数不稳定，主推热门列表）
CLASSES = [
    {"type_id": "hot", "type_name": "热门直播"},
    {"type_id": "all", "type_name": "全部直播"},
]


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _card(it):
    """仅在线房间：必须有 user_id + broad_no，并排除明确下播标记。"""
    if not isinstance(it, dict):
        return None
    uid = str(it.get("user_id") or "").strip()
    bno = str(it.get("broad_no") or "").strip()
    if not uid or not bno:
        return None
    # 常见下播/无效标记
    if it.get("is_password") in (True, 1, "1", "Y", "y"):
        return None
    broad_status = str(it.get("broad_status") or it.get("status") or "").lower()
    if broad_status in ("off", "end", "close", "0", "offline"):
        return None
    if it.get("is_live") in (False, 0, "0", "N", "n"):
        return None
    nick = str(it.get("user_nick") or uid).strip()
    title = str(it.get("title") or nick).strip()
    views = it.get("view_cnt") or 0
    try:
        views = int(views)
    except Exception:
        views = 0
    if views >= 10000:
        remark = "%.1f万观看" % (views / 10000.0)
    else:
        remark = "%s观看" % views
    pic = str(it.get("thumbnail") or "")
    if not pic:
        pic = "https://liveimg.sooplive.com/m/%s" % bno
    return {
        "vod_id": "%s|%s" % (uid, bno),
        "vod_name": "[%s] %s" % (nick, title),
        "vod_pic": pic,
        "vod_remarks": remark,
    }


def _parse_list(payload):
    data = (payload or {}).get("data") or {}
    items = []
    for g in data.get("groups") or []:
        for it in g.get("contents") or []:
            c = _card(it)
            if c:
                items.append(c)
    return items, bool(data.get("has_more_list"))


async def _get_json(url, mobile=True, timeout=12):
    headers = {
        "User-Agent": UA_MOBILE if mobile else UA,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://m.sooplive.com/" if mobile else HOST + "/",
        "Origin": "https://m.sooplive.com" if mobile else HOST,
    }
    res = await OmniBox.request(url, {"method": "GET", "headers": headers, "timeout": timeout})
    text = (res.get("body") or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


async def _post_form(url, form, timeout=12):
    headers = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Referer": PLAY_HOST + "/",
        "Origin": PLAY_HOST,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    res = await OmniBox.request(
        url,
        {"method": "POST", "headers": headers, "body": urlencode(form), "timeout": timeout},
    )
    text = (res.get("body") or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


async def _player_channel(user_id, broad_no, req_type="live", quality="original"):
    form = {
        "bid": user_id,
        "bno": str(broad_no),
        "from_api": "0",
        "mode": "landing",
        "player_type": "html5",
        "pwd": "",
        "stream_type": "common",
        "type": req_type,
    }
    if req_type == "aid":
        form["quality"] = quality
    data = await _post_form(PLAYER_API, form)
    return (data or {}).get("CHANNEL") or {}


async def _resolve_m3u8(user_id, broad_no):
    """取 AID + CDN view_url，拼可播 m3u8。"""
    ch = await _player_channel(user_id, broad_no, "live")
    if not ch or str(ch.get("RESULT")) not in ("1", "1.0", "True"):
        # RESULT 有时缺失但有 BNO
        if not ch.get("BNO") and not ch.get("TS"):
            return "", ch
    aid_ch = await _player_channel(user_id, broad_no, "aid", "original")
    aid = (aid_ch.get("AID") or "").strip()
    rmd = (ch.get("RMD") or STREAM_MGR).rstrip("/")
    bno = str(ch.get("BNO") or broad_no)

    view_url = ""
    for cdn in ("gcp_cdn", "gs_cdn_pc_web", "gs_cdn_mobile_web"):
        try:
            assign = "%s/broad_stream_assign.html?return_type=%s&broad_key=%s-common-master-hls" % (
                rmd,
                cdn,
                bno,
            )
            res = await OmniBox.request(
                assign,
                {
                    "method": "GET",
                    "headers": {
                        "User-Agent": UA,
                        "Referer": PLAY_HOST + "/",
                        "Accept": "application/json,*/*",
                    },
                    "timeout": 10,
                },
            )
            text = (res.get("body") or "").strip()
            if not text.startswith("{"):
                continue
            info = json.loads(text)
            view_url = (info.get("view_url") or info.get("viewurl") or "").strip()
            if view_url:
                break
        except Exception:
            continue

    if not view_url:
        # 退化：TS 字段（部分地区可能 403）
        view_url = (ch.get("TS") or "").strip()

    if view_url and aid:
        view_url = view_url + ("&" if "?" in view_url else "?") + "aid=" + aid
    return view_url, ch


async def home(params, context):
    try:
        await OmniBox.log("info", "[home] from=%s" % (context or {}).get("from", "web"))
        data = await _get_json(API_LIST)
        videos, _ = _parse_list(data)
        return {"class": CLASSES, "list": videos, "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[home] 失败: %s" % e)
        return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    try:
        tid = str((params or {}).get("categoryId") or "hot")
        page = _to_int((params or {}).get("page"), 1) or 1
        await OmniBox.log("info", "[category] %s page=%s" % (tid, page))
        # 接口 page_no 目前返回同一批热门；仍带上参数便于后续兼容
        url = "%s?page_no=%s&order_type=view_cnt" % (API_LIST, page)
        data = await _get_json(url)
        videos, has_more = _parse_list(data)
        pagecount = page + 1 if has_more or len(videos) >= 15 else page
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20,
        }
    except Exception as e:
        await OmniBox.log("error", "[category] 失败: %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 20}


async def detail(params, context):
    try:
        raw = str((params or {}).get("videoId") or "").strip()
        if not raw:
            return {"list": []}
        await OmniBox.log("info", "[detail] %s" % raw)
        if "|" in raw:
            user_id, broad_no = raw.split("|", 1)
        else:
            # 仅 BJ id：从列表里找当前直播
            user_id, broad_no = raw, ""
            data = await _get_json(API_LIST)
            for it in _parse_list(data)[0]:
                if it["vod_id"].startswith(user_id + "|"):
                    broad_no = it["vod_id"].split("|", 1)[1]
                    break
        if not user_id:
            return {"list": []}

        ch = {}
        if broad_no:
            ch = await _player_channel(user_id, broad_no, "live")
        title = str(ch.get("TITLE") or ch.get("BTITLE") or user_id).strip()
        nick = str(ch.get("BJNICK") or user_id).strip()
        bno = str(ch.get("BNO") or broad_no or "").strip()
        pic = "https://liveimg.sooplive.com/m/%s" % bno if bno else ""
        vod_id = "%s|%s" % (user_id, bno) if bno else user_id

        # RESULT 表示频道是否可播；无 BNO 视为未开播
        result_ok = str(ch.get("RESULT") or "") in ("1", "1.0", "True", "")
        online = bool(bno) and result_ok and not str(ch.get("PASSWORD") or "")
        # 若 RESULT 明确失败且无有效 BNO，当作未开播
        if str(ch.get("RESULT")) in ("-1", "0", "False") and not ch.get("BNO"):
            online = False

        vod = {
            "vod_id": vod_id,
            "vod_name": "[%s] %s" % (nick, title),
            "vod_pic": pic,
            "vod_remarks": "直播中" if online else "未开播",
            "vod_content": "BJ: %s / broad: %s" % (user_id, bno),
            "vod_actor": nick,
        }
        if online:
            vod["vod_play_sources"] = [
                {
                    "name": "SOOP",
                    "episodes": [
                        {"name": "直播", "playId": "%s|%s" % (user_id, bno)},
                    ],
                }
            ]
        else:
            vod["vod_play_sources"] = []
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", "[detail] 失败: %s" % e)
        return {"list": []}


async def search(params, context):
    try:
        key = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 20}
        await OmniBox.log("info", "[search] %s" % key)
        # 官方搜索 API 不稳定：用热门列表本地过滤 + 按 BJ id 直查
        data = await _get_json(API_LIST)
        videos, _ = _parse_list(data)
        key_l = key.lower()
        filtered = [
            v
            for v in videos
            if key_l in (v.get("vod_name") or "").lower() or key_l in (v.get("vod_id") or "").lower()
        ]
        # 若关键词像 BJ id，直接尝试拉详情
        if not filtered and key.isalnum():
            ch = await _player_channel(key, "0", "live")
            # broad_no 0 可能无效；仍从列表匹配 user_id
            for v in videos:
                if v["vod_id"].startswith(key + "|"):
                    filtered.append(v)
        return {
            "list": filtered,
            "page": page,
            "pagecount": 1,
            "limit": 20,
            "total": len(filtered),
        }
    except Exception as e:
        await OmniBox.log("error", "[search] 失败: %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 20}


async def play(params, context):
    try:
        play_id = str((params or {}).get("playId") or "").strip()
        flag = str((params or {}).get("flag") or "play")
        if not play_id:
            raise ValueError("playId 为空")
        await OmniBox.log("info", "[play] %s" % play_id)

        if "|" in play_id:
            user_id, broad_no = play_id.split("|", 1)
        else:
            user_id, broad_no = play_id, ""

        if not broad_no:
            # 补全当前直播号
            data = await _get_json(API_LIST)
            for v in _parse_list(data)[0]:
                if v["vod_id"].startswith(user_id + "|"):
                    broad_no = v["vod_id"].split("|", 1)[1]
                    break

        url = ""
        if user_id and broad_no:
            url, _ch = await _resolve_m3u8(user_id, broad_no)

        headers = {
            "User-Agent": UA,
            "Referer": PLAY_HOST + "/",
            "Origin": PLAY_HOST,
        }
        return {
            "urls": [{"name": "直播", "url": url}] if url else [],
            "flag": flag,
            "header": headers,
            "parse": 0 if url else 1,
        }
    except Exception as e:
        await OmniBox.log("error", "[play] 失败: %s" % e)
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
