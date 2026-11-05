# -*- coding: utf-8 -*-
# @name 影探4K
# @version 2.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%94%B5%E5%BD%B1%E7%94%B5%E8%A7%86/影探4K.py
# @description 原 lyyytv 自建 4K CDN 已全 404；改用可用 MacCMS 采集（如意/暴风镜像池）直链 m3u8

"""
影探4K v2.0.0
原站 cms.lyyytv.cn 列表仍在，但 ym4kjx 文件全挂。
改为 MacCMS 采集池，优先返回可播 m3u8。
"""

import json
import re
from urllib.parse import quote

from spider_runner import OmniBox, run

API_POOL = [
    "https://cj.rycjapi.com/api.php/provide/vod/",
    "https://cj.rytvapi.com/api.php/provide/vod/",
    "https://bfzyapi.com/api.php/provide/vod/",
    "http://cj.lziapi.com/api.php/provide/vod/",
    "https://cj.lzcaiji.com/api.php/provide/vod/",
]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_api = API_POOL[0]


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


async def _api_get(params):
    global _api
    bases = [_api] + [x for x in API_POOL if x != _api]
    last = None
    for base in bases:
        try:
            qs = "&".join("%s=%s" % (k, quote(str(v))) for k, v in params.items() if v is not None and v != "")
            url = base.rstrip("/") + ("/?" if "?" not in base else "&") + qs
            # normalize
            if "://" in base and base.endswith("/"):
                url = base + "?" + qs
            else:
                url = base.rstrip("/") + "/?" + qs
            res = await OmniBox.request(
                url,
                {
                    "method": "GET",
                    "headers": {"User-Agent": UA, "Accept": "application/json"},
                    "timeout": 15,
                },
            )
            body = res.get("body") or ""
            if (res.get("statusCode") or 0) != 200 or not body.strip().startswith("{"):
                last = "bad status"
                continue
            data = json.loads(body)
            if not isinstance(data, dict):
                last = "not dict"
                continue
            _api = base
            return data
        except Exception as e:
            last = e
            await OmniBox.log("warn", "[api] %s fail: %s" % (base[:40], e))
            continue
    raise RuntimeError("全部采集镜像失败: %s" % last)


def _card(it):
    return {
        "vod_id": str(it.get("vod_id") or ""),
        "vod_name": str(it.get("vod_name") or "").strip(),
        "vod_pic": str(it.get("vod_pic") or ""),
        "vod_remarks": str(it.get("vod_remarks") or ""),
        "type_name": str(it.get("type_name") or ""),
        "vod_year": str(it.get("vod_year") or ""),
    }


def _is_media(u):
    u = u or ""
    return bool(re.search(r"\.(m3u8|mp4)(\?|$)", u, re.I) or "/index.m3u8" in u)


def _to_play_sources(play_from, play_url):
    names = [x.strip() for x in str(play_from or "").split("$$$") if x.strip()]
    blocks = [x.strip() for x in str(play_url or "").split("$$$") if x.strip()]
    sources = []
    n = max(len(names), len(blocks))
    for i in range(n):
        name = names[i] if i < len(names) else ("线路%s" % (i + 1))
        block = blocks[i] if i < len(blocks) else ""
        eps = []
        for j, seg in enumerate(block.split("#")):
            seg = seg.strip()
            if not seg:
                continue
            if "$" in seg:
                ep_name, pid = seg.split("$", 1)
                ep_name, pid = ep_name.strip(), pid.strip()
            else:
                ep_name, pid = "第%s集" % (j + 1), seg
            if pid:
                eps.append({"name": ep_name or ("第%s集" % (j + 1)), "playId": pid})
        if eps:
            sources.append({"name": name, "episodes": eps})
    # m3u8 优先
    sources.sort(key=lambda s: 0 if _is_media((s["episodes"][0].get("playId") if s["episodes"] else "")) else 1)
    media = [s for s in sources if _is_media((s["episodes"][0].get("playId") if s["episodes"] else ""))]
    return media or sources


async def home(params, context):
    try:
        data = await _api_get({"ac": "list", "pg": "1"})
        classes = []
        for c in data.get("class") or []:
            tid = str(c.get("type_id") or "")
            name = str(c.get("type_name") or "").strip()
            if tid and name:
                classes.append({"type_id": tid, "type_name": name})
        items = [_card(x) for x in (data.get("list") or []) if x]
        items = [x for x in items if x["vod_id"] and x["vod_name"]]
        return {"class": classes, "list": items, "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[home] %s" % e)
        return {"class": [], "list": [], "filters": {}}


async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("tid") or "")
        page = _to_int(p.get("page"), 1) or 1
        data = await _api_get({"ac": "videolist", "t": tid, "pg": str(page)})
        items = [_card(x) for x in (data.get("list") or []) if x]
        items = [x for x in items if x["vod_id"] and x["vod_name"]]
        return {
            "list": items,
            "page": _to_int(data.get("page"), page) or page,
            "pagecount": _to_int(data.get("pagecount"), page) or page,
            "limit": _to_int(data.get("limit"), 20) or 20,
            "total": _to_int(data.get("total"), 0),
        }
    except Exception as e:
        await OmniBox.log("error", "[category] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "limit": 20, "total": 0}


async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or p.get("vod_id") or "").strip()
        if not vid:
            return {"list": []}
        data = await _api_get({"ac": "detail", "ids": vid})
        item = (data.get("list") or [None])[0]
        if not item:
            return {"list": []}
        sources = _to_play_sources(item.get("vod_play_from"), item.get("vod_play_url"))
        vod = {
            "vod_id": str(item.get("vod_id") or vid),
            "vod_name": str(item.get("vod_name") or "").strip(),
            "vod_pic": str(item.get("vod_pic") or ""),
            "vod_year": str(item.get("vod_year") or ""),
            "vod_area": str(item.get("vod_area") or ""),
            "vod_remarks": str(item.get("vod_remarks") or ""),
            "vod_actor": str(item.get("vod_actor") or ""),
            "vod_director": str(item.get("vod_director") or ""),
            "vod_content": re.sub(r"<[^>]+>", "", str(item.get("vod_content") or "")),
            "vod_play_sources": sources,
        }
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", "[detail] %s" % e)
        return {"list": []}


async def search(params, context):
    try:
        p = params or {}
        key = str(p.get("keyword") or p.get("wd") or "").strip()
        page = _to_int(p.get("page"), 1) or 1
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        data = await _api_get({"ac": "list", "wd": key, "pg": str(page)})
        items = [_card(x) for x in (data.get("list") or []) if x]
        items = [x for x in items if x["vod_id"] and x["vod_name"]]
        return {
            "list": items,
            "page": _to_int(data.get("page"), page) or page,
            "pagecount": _to_int(data.get("pagecount"), page) or page,
            "total": _to_int(data.get("total"), 0),
        }
    except Exception as e:
        await OmniBox.log("error", "[search] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}


async def play(params, context):
    try:
        p = params or {}
        play_id = str(p.get("playId") or p.get("url") or "").strip()
        headers = {"User-Agent": UA, "Referer": "https://cj.rycjapi.com/"}
        if not play_id:
            return {"urls": [], "parse": 0, "header": headers}
        # 量子一类 share 页：尝试常见 m3u8 形态（失败则交给 parse）
        if "/share/" in play_id and not _is_media(play_id):
            # 保留原 URL，parse=1 或直接返回
            return {
                "urls": [{"name": "播放", "url": play_id}],
                "parse": 1,
                "header": headers,
            }
        return {
            "urls": [{"name": "播放", "url": play_id}],
            "parse": 0 if _is_media(play_id) else 1,
            "header": headers,
        }
    except Exception as e:
        await OmniBox.log("error", "[play] %s" % e)
        return {"urls": [], "parse": 0, "header": {}}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
