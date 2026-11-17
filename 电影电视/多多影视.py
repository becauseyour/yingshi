# -*- coding: utf-8 -*-
# @name 多多影视
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%94%B5%E5%BD%B1%E7%94%B5%E8%A7%86/多多影视.py
# @description 多多影视站源（OmniBox 适配版）：Vue SPA JSON API + protobuf 解码直链

"""
多多影视 — OmniBox 适配版
保留原 decode/url protobuf 签名与域名轮换逻辑。
"""

import base64
import hashlib
import json
import os
import re
import time

from spider_runner import OmniBox, run

HOSTS = (
    "https://323433ssdfd.top",
    "https://duoduosdf12223234334.top",
    "https://xds2435u23422342342u.top",
    "https://dduotv01.top",
)
HOST = HOSTS[0]
API_PATH = "/api.php/web"
UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
)
WEB_SIGN = "ddtvf65f3a83d6d9ad6f"
CLIENT_TAG = "8f3d2a1c7b6e5d4c9a0b1f2e3d4c5b6a"
FINGERPRINT = "WF-2c064bc5b3400788f31b848849bc3a60f835423ba2dfe69d7ea93974c216e4f2"
SIGN_SALT = "WEB-50a8e9c84a1dc05669a692ded99a2dac46527229e607a7be15db88dbc59059d1"
CLIENT_PKG = "com.web.player"
CATEGORIES = [("1", "电影"), ("2", "剧集"), ("3", "动漫"), ("4", "综艺")]
TID2NAME = dict(CATEGORIES)
PAGE_LIMIT = 24
SEARCH_LIMIT = 15
FETCH_TIMEOUT = 10
FETCH_ATTEMPTS = 4
BLOCK_STATUS = (456, 457, 458)
HARD_REJECT = ("PLATFORM_NOT_ALLOWED", "LOGIN_REQUIRED", "VIP_REQUIRED")

_host = HOST


def _years(floor, tail):
    top = time.localtime().tm_year
    return [str(y) for y in range(top, floor - 1, -1)] + list(tail)


FILTER_SPEC = {
    "电影": {
        "class": ["动作", "喜剧", "爱情", "科幻", "恐怖", "悬疑", "犯罪", "战争", "动画", "冒险", "历史", "灾难", "纪录", "剧情"],
        "area": ["大陆", "香港", "台湾", "美国", "日本", "韩国", "泰国", "印度", "英国", "法国", "德国", "加拿大", "西班牙", "意大利", "澳大利亚"],
        "year": (2016, ["2015-2011", "2010-2000", "90年代", "80年代", "更早"]),
    },
    "剧集": {
        "class": ["爱情", "古装", "武侠", "历史", "家庭", "喜剧", "悬疑", "犯罪", "战争", "奇幻", "科幻", "恐怖"],
        "area": ["大陆", "香港", "台湾", "美国", "日本", "韩国", "泰国", "英国"],
        "year": (2021, ["2020-2016", "2015-2011", "2010-2000", "更早"]),
    },
    "综艺": {
        "class": ["真人秀", "音乐", "脱口秀", "歌舞", "爱情"],
        "area": ["大陆", "香港", "台湾", "美国", "日本", "韩国"],
        "year": (2011, ["更早"]),
    },
    "动漫": {
        "class": ["冒险", "奇幻", "科幻", "武侠", "悬疑"],
        "area": ["大陆", "日本", "欧美"],
        "year": (2011, ["更早"]),
    },
}
SORT_OPTIONS = [("默认", ""), ("人气", "hits"), ("最新", "time"), ("评分", "score"), ("年份", "year")]


def _pb_varint(value):
    out = bytearray()
    n = int(value) & 0xFFFFFFFFFFFFFFFF
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _pb_read_varint(raw, pos):
    value, shift, size = 0, 0, len(raw)
    while pos < size and shift < 64:
        b = raw[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        if not b & 0x80:
            return value, pos
        shift += 7
    return None, pos


def _pb_parse(raw):
    if isinstance(raw, str):
        raw = raw.encode("utf-8", "replace")
    out = {}
    pos, size = 0, len(raw or b"")
    while pos < size:
        key, pos = _pb_read_varint(raw, pos)
        if key is None:
            break
        num, wire = key >> 3, key & 7
        if wire == 0:
            value, pos = _pb_read_varint(raw, pos)
            if value is None:
                break
            out[num] = value
        elif wire == 2:
            length, pos = _pb_read_varint(raw, pos)
            if length is None or pos + length > size:
                break
            out[num] = raw[pos:pos + length].decode("utf-8", "replace")
            pos += length
        elif wire == 5:
            pos += 4
        elif wire == 1:
            pos += 8
        else:
            break
    return out


def _to_page(pg):
    try:
        return max(int(str(pg)), 1)
    except (TypeError, ValueError):
        return 1


def _pagecount(page_no, got, limit):
    return page_no + 1 if got >= max(1, int(limit * 3) // 4) else page_no


def _safe(value):
    return str(value or "").replace("$", "\uff04").replace("#", "\uff03").strip()


def _clean(value):
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _pack(frm, vid, ep_no, token):
    raw = "%s\n%s\n%d\n%s" % (frm, vid, ep_no, token)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _unpack(blob):
    text = str(blob or "").strip()
    if not text:
        return "", "", 0, ""
    text += "=" * (-len(text) % 4)
    try:
        raw = base64.urlsafe_b64decode(text.encode("ascii")).decode("utf-8", "replace")
    except Exception:
        return "", "", 0, ""
    parts = raw.split("\n", 3)
    if len(parts) != 4:
        return "", "", 0, ""
    frm, vid, ep_no, token = parts
    try:
        ep_no = int(ep_no)
    except (TypeError, ValueError):
        ep_no = 0
    return frm, vid, ep_no, token


def _cards(items):
    out = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        vid, name = item.get("vod_id"), item.get("vod_name")
        if vid is None or not name:
            continue
        out.append({
            "vod_id": str(vid),
            "vod_name": str(name).strip(),
            "vod_pic": str(item.get("vod_pic") or ""),
            "vod_remarks": str(item.get("vod_remarks") or ""),
        })
    return out


def _api_headers(host=None):
    return {
        "User-Agent": UA,
        "web-sign": WEB_SIGN,
        "X-Client": CLIENT_TAG,
        "Accept": "application/json, text/plain, */*",
        "Referer": (host or _host) + "/",
    }


async def _api(path, params=None):
    global _host
    hosts = [_host] + [h for h in HOSTS if h != _host]
    for attempt in range(FETCH_ATTEMPTS):
        host = hosts[attempt % len(HOSTS)]
        try:
            url = host + API_PATH + path
            if params:
                from urllib.parse import urlencode
                url += "?" + urlencode({k: str(v) for k, v in params.items()})
            res = await OmniBox.request(
                url,
                {"method": "GET", "headers": _api_headers(host), "timeout": FETCH_TIMEOUT},
            )
            status = res.get("statusCode") or 0
            text = str(res.get("body") or "").strip()
            data = json.loads(text) if text.startswith("{") else None
            if (
                isinstance(data, dict)
                and status not in BLOCK_STATUS
                and data.get("code") not in BLOCK_STATUS
            ):
                _host = host
                return data
        except Exception:
            pass
    return {}


def _decode_body(token, frm):
    if not token:
        return b""
    now = int(time.time() * 1000)
    nonce = os.urandom(16).hex()
    source = "finger=%s&id=%s&nonce=%s&sk=%s&time=%d&v=1" % (
        FINGERPRINT, CLIENT_PKG, nonce, SIGN_SALT, now
    )
    sign = hashlib.sha256(source.encode("utf-8")).hexdigest().upper()
    chunks = []
    for num, value in ((1, token), (2, frm or ""), (3, now), (4, nonce), (5, sign), (6, CLIENT_PKG), (7, 1)):
        if isinstance(value, int):
            chunks.append(_pb_varint((num << 3) | 0) + _pb_varint(value))
        else:
            raw = str(value).encode("utf-8")
            chunks.append(_pb_varint((num << 3) | 2) + _pb_varint(len(raw)) + raw)
    return b"".join(chunks)


async def _decode(token, frm):
    global _host
    body = _decode_body(token, frm)
    if not body:
        return ""
    hosts = [_host] + [h for h in HOSTS if h != _host]
    for attempt in range(FETCH_ATTEMPTS):
        host = hosts[attempt % len(HOSTS)]
        headers = _api_headers(host)
        headers["Content-Type"] = "application/x-protobuf"
        headers["Accept"] = "application/x-protobuf"
        try:
            # OmniBox may expect string body; pass latin1-safe representation
            res = await OmniBox.request(
                host + API_PATH + "/decode/url",
                {
                    "method": "POST",
                    "headers": headers,
                    "body": body.decode("latin1"),
                    "timeout": FETCH_TIMEOUT,
                },
            )
            raw = res.get("body") or ""
            if isinstance(raw, str):
                raw = raw.encode("latin1", "replace")
            fields = _pb_parse(raw)
            if fields.get(1) == 1 and fields.get(3):
                _host = host
                return str(fields[3])
            if str(fields.get(2) or "") in HARD_REJECT:
                return ""
        except Exception:
            pass
    return ""


def _build_filters(classes):
    filters = {}
    for item in classes:
        spec = FILTER_SPEC.get(item.get("type_name"))
        if not spec:
            continue
        groups = []
        for key, label in (("class", "类型"), ("area", "地区"), ("year", "年份")):
            values = spec.get(key)
            if key == "year" and values:
                values = _years(values[0], values[1])
            if not values:
                continue
            groups.append({
                "key": key,
                "name": label,
                "value": [{"n": "全部", "v": ""}] + [{"n": v, "v": v} for v in values],
            })
        groups.append({
            "key": "sort",
            "name": "排序",
            "value": [{"n": n, "v": v} for n, v in SORT_OPTIONS],
        })
        filters[str(item.get("type_id"))] = groups
    return filters


def _lines_to_sources(payload, raw, vid):
    froms = [x.strip() for x in str(raw.get("vod_play_from") or "").split("$$$")]
    segs = [x.strip() for x in str(raw.get("vod_play_url") or "").split("$$$")]
    shows = {}
    for item in payload.get("vodplayer") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("from") or "").strip()
        show = str(item.get("show") or "").strip()
        if key and show:
            shows[key] = show
    sources = []
    used = set()
    for index, frm in enumerate(froms):
        if not frm or index >= len(segs) or not segs[index]:
            continue
        name = _safe(shows.get(frm) or frm) or frm
        if name in used:
            name = frm
        used.add(name)
        episodes = []
        for ep_i, ep in enumerate(segs[index].split("#"), 1):
            if not ep or "$" not in ep:
                continue
            title, token = ep.rsplit("$", 1)
            token = token.strip()
            if not token:
                continue
            title = _safe(title) or ("第%d集" % ep_i)
            episodes.append({"name": title, "playId": _pack(frm, vid, ep_i, token)})
        if episodes:
            sources.append({"name": name, "episodes": episodes})
    return sources


async def home(params, context):
    try:
        await OmniBox.log("info", f"[home] from={(context or {}).get('from', 'web')}")
        payload = await _api("/index/home")
        classes = []
        data = payload.get("data")
        categories = data.get("categories") if isinstance(data, dict) else None
        for item in categories or []:
            if not isinstance(item, dict):
                continue
            tid, name = item.get("type_id"), item.get("type_name")
            if tid is None or not name:
                continue
            classes.append({"type_id": str(tid), "type_name": str(name)})
        if not classes:
            classes = [{"type_id": tid, "type_name": name} for tid, name in CATEGORIES]
        cards = []
        if isinstance(data, dict):
            groups = [data.get("recommend")]
            for cat in data.get("categories") or []:
                if isinstance(cat, dict):
                    groups.append(cat.get("videos"))
            seen = set()
            for group in groups:
                for card in _cards(group if isinstance(group, list) else []):
                    if card["vod_id"] in seen:
                        continue
                    seen.add(card["vod_id"])
                    cards.append(card)
        return {"class": classes, "list": cards, "filters": _build_filters(classes)}
    except Exception as e:
        await OmniBox.log("error", f"[home] 失败: {e}")
        return {"class": [{"type_id": t, "type_name": n} for t, n in CATEGORIES], "list": [], "filters": {}}


async def category(params, context):
    try:
        tid = str((params or {}).get("categoryId") or "1")
        page = _to_page((params or {}).get("page"))
        extend = (params or {}).get("filters") or {}
        await OmniBox.log("info", f"[category] categoryId={tid}, page={page}")
        type_name = TID2NAME.get(tid, tid)
        req = {"type_name": type_name, "type_id": tid, "page": page, "sort": "hits"}
        for key in ("class", "area", "year", "sort"):
            value = extend.get(key) if isinstance(extend, dict) else None
            if value not in (None, ""):
                req[key] = value
        payload = await _api("/filter/vod", req)
        items = _cards(payload.get("data"))
        return {
            "list": items,
            "page": page,
            "pagecount": _pagecount(page, len(items), PAGE_LIMIT),
            "limit": PAGE_LIMIT,
            "total": 9999,
        }
    except Exception as e:
        await OmniBox.log("error", f"[category] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": PAGE_LIMIT}


async def detail(params, context):
    try:
        vid = str((params or {}).get("videoId") or "")
        found = re.search(r"(\d+)", vid)
        vid = found.group(1) if found else vid
        if not vid:
            return {"list": []}
        await OmniBox.log("info", f"[detail] videoId={vid}")
        payload = await _api("/vod/get_detail", {"vod_id": vid})
        rows = payload.get("data")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return {"list": []}
        raw = rows[0]
        vod = {
            "vod_id": vid,
            "vod_name": _clean(raw.get("vod_name")),
            "vod_pic": str(raw.get("vod_pic") or ""),
            "vod_year": _clean(raw.get("vod_year")),
            "vod_area": _clean(raw.get("vod_area")),
            "vod_remarks": _clean(raw.get("vod_remarks")),
            "vod_actor": _clean(raw.get("vod_actor")),
            "vod_director": _clean(raw.get("vod_director")),
            "vod_content": _clean(raw.get("vod_content")),
        }
        sources = _lines_to_sources(payload, raw, vid)
        if sources:
            vod["vod_play_sources"] = sources
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] 失败: {e}")
        return {"list": []}


async def search(params, context):
    try:
        key = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_page((params or {}).get("page"))
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": SEARCH_LIMIT}
        await OmniBox.log("info", f"[search] keyword={key}, page={page}")
        payload = await _api("/search/index", {"wd": key, "page": page, "limit": SEARCH_LIMIT})
        items = _cards(payload.get("data"))
        return {
            "list": items,
            "page": page,
            "pagecount": _pagecount(page, len(items), SEARCH_LIMIT),
            "limit": SEARCH_LIMIT,
            "total": 9999,
        }
    except Exception as e:
        await OmniBox.log("error", f"[search] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": SEARCH_LIMIT}


async def play(params, context):
    try:
        play_id = str((params or {}).get("playId") or "").strip()
        flag = str((params or {}).get("flag") or "play")
        if not play_id:
            raise ValueError("playId 为空")
        await OmniBox.log("info", f"[play] playId={play_id[:80]}")
        frm, vid, ep_no, token = _unpack(play_id)
        if not token:
            token, frm = play_id, flag
            vid, ep_no = "", 0
        url = await _decode(token, frm) if token else ""
        headers = {"User-Agent": UA}
        if url:
            return {
                "urls": [{"name": "播放", "url": url}],
                "flag": flag,
                "header": headers,
                "parse": 0,
            }
        page = (_host + "/") if not vid else "%s/play/%s" % (_host, vid)
        if vid and frm:
            page += "#sid=%s&nid=%d" % (frm, max(int(ep_no or 0), 1))
        return {
            "urls": [{"name": "播放", "url": page}],
            "flag": flag,
            "header": headers,
            "parse": 1,
        }
    except Exception as e:
        await OmniBox.log("error", f"[play] 失败: {e}")
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
