# -*- coding: utf-8 -*-
# @name EcoHub影视
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/电影电视/EcoHub影视.py
# @description EcoHub影视（OmniBox）

import re
import json
from urllib.parse import urlencode
from spider_runner import OmniBox, run

HOST = "https://eco.fe-spark.cn"
API = HOST + "/api"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

FALLBACK_CATS = [
    {"type_id": "1", "type_name": "动漫"},
    {"type_id": "8", "type_name": "电影"},
    {"type_id": "26", "type_name": "连续剧"},
    {"type_id": "36", "type_name": "综艺"},
    {"type_id": "41", "type_name": "体育"},
    {"type_id": "43", "type_name": "AI漫剧"},
]

async def _api(path, params=None):
    try:
        url = API + path
        if params:
            url += "?" + urlencode({k: v for k, v in params.items() if v not in (None, "")})
        res = await OmniBox.request(url, {"method": "GET", "headers": {"User-Agent": UA, "Referer": HOST + "/", "Origin": HOST}, "timeout": 15})
        body = res.get("body") or ""
        if body.startswith("{"):
            return json.loads(body).get("data") or {}
        return {}
    except Exception:
        return {}

def _cards(arr):
    out, seen = [], set()
    for it in arr or []:
        vid = str(it.get("id") or it.get("mid") or "")
        if not vid or vid in seen:
            continue
        seen.add(vid)
        pic = it.get("picture") or it.get("poster") or ""
        if pic and not pic.startswith("http"):
            pic = HOST + pic if pic.startswith("/") else pic
        out.append({"vod_id": vid, "vod_name": str(it.get("name") or ""), "vod_pic": pic, "vod_remarks": str(it.get("remarks") or "")})
    return out

async def home(params, context):
    try:
        data = await _api("/index")
        cats = []
        for c in ((data.get("category") or {}).get("children") or []):
            if c.get("show") is False:
                continue
            cats.append({"type_id": str(c.get("id")), "type_name": str(c.get("name") or "")})
        if not cats:
            cats = FALLBACK_CATS
        arr = []
        for b in data.get("banners") or []:
            arr.append({"id": b.get("mid") or b.get("id"), "name": b.get("name"), "picture": b.get("picture"), "remarks": b.get("remark")})
        for block in data.get("content") or []:
            arr.extend(block.get("hot") or [])
            arr.extend(block.get("movies") or [])
        return {"class": cats, "list": _cards(arr)[:40], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] {e}")
        return {"class": FALLBACK_CATS, "list": [], "filters": {}}

async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("type_id") or "1")
        page = int(p.get("page") or 1)
        data = await _api("/filmClassifySearch", {"Pid": tid, "current": page})
        items = _cards(data.get("list"))
        pc = int((data.get("page") or {}).get("pageCount") or page)
        return {"list": items, "page": page, "pagecount": pc, "total": len(items) * pc}
    except Exception as e:
        await OmniBox.log("error", f"[category] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def search(params, context):
    try:
        p = params or {}
        key = (p.get("keyword") or "").strip()
        page = int(p.get("page") or 1)
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        data = await _api("/searchFilm", {"keyword": key, "current": page})
        items = _cards(data.get("list"))
        return {"list": items, "page": page, "pagecount": int((data.get("page") or {}).get("pageCount") or 1), "total": len(items)}
    except Exception as e:
        await OmniBox.log("error", f"[search] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or "").strip()
        if not vid:
            return {"list": []}
        data = await _api("/filmPlayInfo", {"id": vid})
        detail = data.get("detail") or {}
        d = detail.get("descriptor") or {}
        sources = detail.get("list") or []
        if not sources:
            froms = detail.get("playFrom") or []
            lists = detail.get("playList") or []
            for i, eps in enumerate(lists):
                sources.append({"name": froms[i] if i < len(froms) else f"线路{i+1}", "linkList": eps})
        play_sources = []
        for src in sources:
            eps = []
            for ep in src.get("linkList") or []:
                name = str(ep.get("episode") or "播放")
                link = (ep.get("link") or "").strip()
                if link:
                    eps.append({"name": name, "playId": link})
            if eps:
                play_sources.append({"name": str(src.get("name") or "线路"), "episodes": eps})
        if not play_sources:
            play_sources = [{"name": "默认", "episodes": [{"name": "播放", "playId": vid}]}]
        return {"list": [{"vod_id": vid, "vod_name": str(detail.get("name") or vid), "vod_pic": detail.get("picture") or "", "vod_content": str(d.get("content") or ""), "vod_play_sources": play_sources}]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] {e}")
        return {"list": []}

async def play(params, context):
    try:
        p = params or {}
        pid = str(p.get("playId") or "").strip()
        headers = {"User-Agent": UA, "Referer": HOST + "/"}
        if pid.startswith("http"):
            return {"urls": [{"name": "播放", "url": pid}], "parse": 0 if re.search(r"\.(m3u8|mp4)", pid, re.I) else 1, "header": headers}
        return {"urls": [{"name": "播放", "url": pid}], "parse": 1, "header": headers}
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
