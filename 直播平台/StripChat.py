# -*- coding: utf-8 -*-
# @name StripChat
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%9B%B4%E6%92%AD%E5%B9%B3%E5%8F%B0/StripChat.py
# @description StripChat 直播；仅展示在线房间

import json
import re
from urllib.parse import quote

from spider_runner import OmniBox, run

HOSTS = [
    "https://zh.stripchat.com",
    "https://zh.stripchat.global",
    "https://zh.stripol.com",
]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:153.0) Gecko/20100101 Firefox/153.0"
CDN = "doppiocdn.org"

CLASSES = [
    {"type_id": "girls", "type_name": "女主播"},
    {"type_id": "couples", "type_name": "情侣"},
    {"type_id": "men", "type_name": "男主播"},
    {"type_id": "trans", "type_name": "跨性别"},
]

TAG_VALUES = [
    {"n": "全部", "v": ""},
    {"n": "新主播", "v": "autoTagNew"},
    {"n": "推荐", "v": "recommended"},
    {"n": "VR", "v": "autoTagVr"},
    {"n": "亚洲人", "v": "ethnicityAsian"},
    {"n": "🇨🇳中国", "v": "tagLanguageChinese"},
    {"n": "🇯🇵日本", "v": "tagLanguageJapanese"},
    {"n": "🇰🇷韩国", "v": "tagLanguageKorean"},
    {"n": "🇷🇺俄罗斯", "v": "tagLanguageRussianSpeaking"},
    {"n": "🇺🇸美国", "v": "tagLanguageUSModels"},
    {"n": "白人", "v": "ethnicityWhite"},
    {"n": "拉丁", "v": "ethnicityLatino"},
    {"n": "黑人", "v": "ethnicityEbony"},
    {"n": "18+", "v": "ageTeen"},
    {"n": "青年", "v": "ageYoung"},
]


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _flag(code):
    code = (code or "").strip()
    if len(code) == 2 and code.isalpha():
        return "".join(chr(ord(c.upper()) - ord("A") + 0x1F1E6) for c in code)
    return ""


def _status_remark(status, viewers=0):
    if status == "public":
        st = "🔴直播中"
    elif status in ("groupShow", "ticket"):
        st = "🎫付费房"
    elif status == "off":
        st = "⚫已下播"
    else:
        st = status or "未知"
    return "%s 👤%s人" % (st, viewers) if viewers else st


async def _api(path):
    last = {}
    for host in HOSTS:
        url = host.rstrip("/") + path
        headers = {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Origin": host,
            "Referer": host + "/",
        }
        try:
            res = await OmniBox.request(
                url, {"method": "GET", "headers": headers, "timeout": 12}
            )
            body = res.get("body") or ""
            if res.get("statusCode") != 200 or not body:
                continue
            data = json.loads(body)
            if isinstance(data, dict) and data:
                # 记住可用 host：移到队首
                if HOSTS[0] != host:
                    HOSTS.remove(host)
                    HOSTS.insert(0, host)
                return data, host
        except Exception as e:
            last = {"err": str(e)}
            continue
    return last, HOSTS[0]


def _model_item(m):
    status = m.get("status") or "off"
    viewers = m.get("viewersCount") or 0
    is_live = bool(m.get("isLive")) or status in ("public", "groupShow", "ticket")
    mid = str(m.get("id") or "")
    name = "%s%s" % (_flag(m.get("country")), m.get("username") or mid)
    pic = "https://img.%s/snapshot/%s/%s" % (
        CDN,
        mid,
        m.get("snapshotTimestamp") or "",
    )
    return {
        "vod_id": mid,
        "vod_name": name,
        "vod_pic": pic,
        "vod_remarks": _status_remark(status, viewers),
        "vod_tag": "online" if is_live and status == "public" else status,
        "_live": is_live and status == "public",
    }


async def home(params, context):
    filters = {
        tid: [{"key": "tag", "name": "标签", "value": TAG_VALUES}]
        for tid in ("girls", "couples", "men", "trans")
    }
    try:
        data, _ = await _api(
            "/api/front/models?improveTs=false&removeShows=false&limit=40&offset=0"
            "&primaryTag=girls&sortBy=stripRanking&rcmGrp=A&rbCnGr=true&prxCnGr=false&nic=false"
        )
        items = []
        for m in data.get("models") or []:
            it = _model_item(m)
            if it.get("_live"):
                items.append({k: v for k, v in it.items() if not k.startswith("_")})
        return {"class": CLASSES, "list": items, "filters": filters}
    except Exception as e:
        await OmniBox.log("error", "[home] %s" % e)
        return {"class": CLASSES, "list": [], "filters": filters}


async def category(params, context):
    p = params or {}
    tid = str(p.get("categoryId") or p.get("tid") or "girls")
    page = _to_int(p.get("page"), 1) or 1
    tag = ""
    if isinstance(p.get("filters"), dict):
        tag = str(p["filters"].get("tag") or "")
    tag = tag or str(p.get("tag") or "")

    # 搜索假分类 search <tag> <key>
    if tid.startswith("search "):
        parts = tid.split(maxsplit=2)
        if len(parts) >= 3:
            _, primary, key = parts
            path = (
                "/api/front/v4/models/search/group/username?query=%s&limit=100&primaryTag=%s"
                % (quote(key), quote(primary))
            )
            data, _ = await _api(path)
            items = []
            for m in data.get("models") or []:
                it = _model_item(m)
                if it.get("_live"):
                    items.append({k: v for k, v in it.items() if not k.startswith("_")})
            return {
                "list": items,
                "page": page,
                "pagecount": 1,
                "limit": 100,
                "total": len(items),
            }

    limit, offset = 60, 60 * (page - 1)
    path = (
        "/api/front/models?improveTs=false&removeShows=false&limit=%s&offset=%s"
        "&primaryTag=%s&sortBy=stripRanking&rcmGrp=A&rbCnGr=true&prxCnGr=false&nic=false"
        % (limit, offset, quote(tid))
    )
    if tag:
        path += "&filterGroupTags=[[\"%s\"]]" % tag.replace('"', "")
    try:
        data, _ = await _api(path)
        items = []
        for m in data.get("models") or []:
            it = _model_item(m)
            # 只保留公开在线
            if it.get("_live"):
                items.append({k: v for k, v in it.items() if not k.startswith("_")})
        total = int(data.get("filteredCount") or len(items))
        pagecount = max(1, (total + limit - 1) // limit)
        return {
            "list": items,
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": total,
        }
    except Exception as e:
        await OmniBox.log("error", "[category] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "limit": 60, "total": 0}


async def detail(params, context):
    vid = str(
        (params or {}).get("videoId")
        or (params or {}).get("id")
        or (params or {}).get("vod_id")
        or ""
    ).strip()
    if not vid:
        return {"list": []}
    # 详情简化：三线路 playId
    sources = [
        {
            "name": "主线路",
            "episodes": [{"name": "直播", "playId": "main_%s" % vid}],
        },
        {
            "name": "备用1",
            "episodes": [{"name": "直播", "playId": "sacf_%s" % vid}],
        },
        {
            "name": "备用2",
            "episodes": [{"name": "直播", "playId": "dop_%s" % vid}],
        },
    ]
    return {
        "list": [
            {
                "vod_id": vid,
                "vod_name": "StripChat %s" % vid,
                "vod_pic": "https://img.%s/snapshot/%s/" % (CDN, vid),
                "vod_remarks": "🔴直播",
                "vod_content": "StripChat 直播流",
                "vod_play_sources": sources,
            }
        ]
    }


async def search(params, context):
    key = str((params or {}).get("keyword") or "").strip()
    if not key:
        return {"list": []}
    # 返回四个主分类入口，点进后用 search 假 id 查
    items = []
    for c in CLASSES:
        items.append(
            {
                "vod_id": "search %s %s" % (c["type_id"], key),
                "vod_name": "搜索「%s」· %s" % (key, c["type_name"]),
                "vod_pic": "",
                "vod_remarks": "点进查看结果",
            }
        )
    return {"list": items, "page": 1, "pagecount": 1}


async def play(params, context):
    play_id = str(
        (params or {}).get("playId")
        or (params or {}).get("url")
        or (params or {}).get("id")
        or ""
    ).strip()
    headers = {
        "User-Agent": UA,
        "Origin": HOSTS[0],
        "Referer": HOSTS[0] + "/",
    }
    m = re.search(r"(?:main_|sacf_|dop_)?(\d+)$", play_id)
    if not m:
        return {"urls": [], "parse": 0, "header": headers}
    sid = m.group(1)

    candidates = []
    if play_id.startswith("sacf_"):
        candidates.append(
            "https://edge-hls.sacfedge.com/hls/%s/master/%s_auto.m3u8?playlistType=lowLatency"
            % (sid, sid)
        )
    if play_id.startswith("dop_") or play_id.startswith("main_") or True:
        candidates.append(
            "https://edge-hls.%s/hls/%s/master/%s_auto.m3u8?playlistType=lowLatency"
            % (CDN, sid, sid)
        )
        candidates.append(
            "https://edge-hls.sacfedge.com/hls/%s/master/%s_auto.m3u8?playlistType=lowLatency"
            % (sid, sid)
        )

    urls = []
    for m3 in candidates:
        try:
            res = await OmniBox.request(
                m3, {"method": "GET", "headers": headers, "timeout": 10}
            )
            body = res.get("body") or ""
            if res.get("statusCode") == 200 and "#EXT" in body:
                # 解析清晰度
                lines = body.strip().split("\n")
                for i, line in enumerate(lines):
                    if "#EXT-X-STREAM-INF" in line and i + 1 < len(lines):
                        nm = "自动"
                        mm = re.search(r'NAME="([^"]+)"', line)
                        if mm:
                            nm = mm.group(1)
                        stream = lines[i + 1].strip()
                        if stream and not stream.startswith("#"):
                            if stream.startswith("http"):
                                urls.append({"name": nm, "url": stream})
                            else:
                                # 相对路径
                                base = m3.rsplit("/", 1)[0] + "/"
                                urls.append({"name": nm, "url": base + stream})
                if not urls:
                    urls.append({"name": "直播", "url": m3})
                break
        except Exception:
            continue

    if not urls:
        # 仍返回 master，交给客户端
        urls = [{"name": "直播", "url": candidates[0]}]
        return {"urls": urls, "parse": 1, "header": headers}
    return {"urls": urls, "parse": 0, "header": headers}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
