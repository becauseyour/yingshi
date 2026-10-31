# -*- coding: utf-8 -*-
# @name 野果短剧
# @version 1.2.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/%E9%87%8E%E6%9E%9C%E7%9F%AD%E5%89%A7.py
# @description 野果短剧 AES 接口；errcode+data 解密

import base64
import json
from urllib.parse import urlencode

from spider_runner import OmniBox, run

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as sym_padding
except Exception:
    Cipher = None

API = "https://www.yeguodj.com/api.php"
SITE = "https://www.yeguodj.com"
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
API_KEY = b"2acf7e91e9864673"
API_IV = b"1c29882d3ddfcfd6"
BASE = {
    "bundleId": "com.pwa.mater",
    "version": "1.3.2",
    "oauth_type": "web",
    "language": "zh",
    "via": "pwa",
    "oauth_id": "7d05538c4b8a5e74e82f93c0dab0163c",
    "token": "",
    "trace_id": "7d05538c4b8a5e74e82f93c0dab0163c",
}

CLASSES = [
    {"type_id": "explore", "type_name": "发现"},
    {"type_id": "dushi", "type_name": "都市"},
    {"type_id": "xiandai", "type_name": "现代"},
    {"type_id": "xiaoyuan", "type_name": "校园"},
    {"type_id": "gudai", "type_name": "古代"},
    {"type_id": "xiangcun", "type_name": "乡村"},
    {"type_id": "zhichang", "type_name": "职场"},
    {"type_id": "chongsheng", "type_name": "重生"},
    {"type_id": "chuanyue", "type_name": "穿越"},
    {"type_id": "xitong", "type_name": "系统"},
    {"type_id": "nixi", "type_name": "逆袭"},
    {"type_id": "mogai", "type_name": "魔改"},
]
# 筛选字段映射（后台 bg / setting id）
BG_MAP = {"dushi": 40, "xiandai": 39, "xiaoyuan": 47, "gudai": 41, "xiangcun": 42, "zhichang": 44}
SETTING_MAP = {"chongsheng": 26, "chuanyue": 27, "xitong": 28, "nixi": 53, "mogai": 56}


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _aes_decrypt(cipher_b64):
    if not Cipher or not cipher_b64:
        return ""
    raw = base64.b64decode(cipher_b64)
    decryptor = Cipher(algorithms.AES(API_KEY), modes.CBC(API_IV)).decryptor()
    plain = decryptor.update(raw) + decryptor.finalize()
    unpadder = sym_padding.PKCS7(128).unpadder()
    return (unpadder.update(plain) + unpadder.finalize()).decode("utf-8", "ignore")


async def _api(path, extra=None):
    payload = dict(BASE)
    if extra:
        payload.update(extra)
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": SITE + "/",
        "Origin": SITE,
    }
    res = await OmniBox.request(
        API + path,
        {
            "method": "POST",
            "headers": headers,
            "body": urlencode(payload),
            "timeout": 15,
        },
    )
    body = res.get("body") or ""
    if not body:
        return {}
    try:
        j = json.loads(body)
    except Exception:
        return {}
    data = j.get("data")
    if isinstance(data, str) and len(data) > 16:
        try:
            plain = json.loads(_aes_decrypt(data))
            if isinstance(plain, dict) and "data" in plain:
                return plain["data"] if isinstance(plain["data"], dict) else plain
            return plain if isinstance(plain, dict) else {}
        except Exception as e:
            await OmniBox.log("warn", "[aes] %s" % e)
            return {}
    return data if isinstance(data, dict) else {}


def _item(it):
    vid = str(it.get("video_id") or it.get("id") or "")
    return {
        "vod_id": vid,
        "vod_name": it.get("title") or vid,
        "vod_pic": it.get("cover") or it.get("cover_img") or "",
        "vod_remarks": it.get("play_count_text")
        or it.get("serialize_status_text")
        or "",
    }


async def home(params, context):
    try:
        data = await _api("/theater/exploreList", {"page": "1", "limit": "20"})
        items = [_item(x) for x in (data.get("list") or [])]
        return {"class": CLASSES, "list": items, "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[home] %s" % e)
        return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    p = params or {}
    tid = str(p.get("categoryId") or p.get("tid") or "explore")
    page = _to_int(p.get("page"), 1) or 1
    extra = {"page": str(page), "limit": "20"}
    if tid in BG_MAP:
        extra["background"] = str(BG_MAP[tid])
    elif tid in SETTING_MAP:
        extra["setting"] = str(SETTING_MAP[tid])
    try:
        data = await _api("/theater/exploreList", extra)
        items = [_item(x) for x in (data.get("list") or [])]
        total = _to_int(data.get("total"), len(items))
        limit = _to_int(data.get("limit"), 20) or 20
        pagecount = max(1, (total + limit - 1) // limit) if total else page
        return {
            "list": items,
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": total,
        }
    except Exception as e:
        await OmniBox.log("error", "[category] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "limit": 20, "total": 0}


async def detail(params, context):
    vid = str(
        (params or {}).get("videoId")
        or (params or {}).get("id")
        or (params or {}).get("vod_id")
        or ""
    ).strip()
    if not vid:
        return {"list": []}
    try:
        data = await _api(
            "/playlet/detail",
            {
                "video_id": vid,
                "id": vid,
                "episode_id": "0",
                "related_limit": "0",
            },
        )
        if not data:
            return {"list": []}
        eps = []
        for ep in data.get("episodes") or []:
            eid = str(ep.get("id") or ep.get("episode_id") or "")
            name = ep.get("title") or ("第%s集" % (ep.get("sort") or len(eps) + 1))
            if eid:
                eps.append({"name": str(name), "playId": "%s_%s" % (vid, eid)})
        if not eps:
            eps = [{"name": "第1集", "playId": "%s_0" % vid}]
        vod = {
            "vod_id": vid,
            "vod_name": data.get("title") or vid,
            "vod_pic": data.get("cover") or "",
            "vod_remarks": data.get("serialize_status_text") or "",
            "vod_content": data.get("description") or "",
            "vod_play_sources": [{"name": "野果", "episodes": eps}],
        }
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", "[detail] %s" % e)
        return {"list": []}


async def search(params, context):
    key = str((params or {}).get("keyword") or "").strip()
    page = _to_int((params or {}).get("page"), 1) or 1
    if not key:
        return {"list": []}
    try:
        data = await _api(
            "/search/result",
            {"keyword": key, "page": str(page), "tab": "video"},
        )
        items = [_item(x) for x in (data.get("list") or [])]
        return {"list": items, "page": page, "pagecount": page + (1 if items else 0)}
    except Exception as e:
        await OmniBox.log("error", "[search] %s" % e)
        return {"list": []}


async def play(params, context):
    play_id = str(
        (params or {}).get("playId")
        or (params or {}).get("url")
        or (params or {}).get("id")
        or ""
    ).strip()
    headers = {"User-Agent": UA, "Referer": SITE + "/"}
    if not play_id:
        return {"urls": [], "parse": 0, "header": headers}
    if play_id.startswith("http"):
        return {"urls": [{"name": "播放", "url": play_id}], "parse": 0, "header": headers}
    parts = play_id.split("_", 1)
    vid, eid = parts[0], (parts[1] if len(parts) > 1 else "0")
    try:
        data = await _api(
            "/playlet/play",
            {"video_id": vid, "episode_id": eid},
        )
        url = data.get("video_url") or data.get("video_url_h265") or ""
        if url:
            return {
                "urls": [{"name": "播放", "url": url}],
                "parse": 0,
                "header": headers,
            }
    except Exception as e:
        await OmniBox.log("error", "[play] %s" % e)
    return {"urls": [], "parse": 0, "header": headers}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
