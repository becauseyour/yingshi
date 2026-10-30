# -*- coding: utf-8 -*-
# @name 萝莉岛
# @version 1.1.0
# @description 萝莉岛 API 采集；域名池自动切换 OmniBox 适配版

import json
import re
from urllib.parse import quote, urlencode

from spider_runner import OmniBox, run

UA = (
    "Mozilla/5.0 (Linux; Android 12; TFY-AN00) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Version/4.0 Chrome/92.0.4515.105 Mobile Safari/537.36"
)
DOMAIN_API = "https://lwncnss3api.cc/api/getapi.php"
BACKUP = [
    "dag29jmgma1g.site",
    "ldngksapi.cc",
    "lagh23ksapi.cc",
    "ldagwhdgpi.cc",
    "lwetasdf3api.cc",
    "lwasga289api.cc",
    "lw2wthchhaapi.cc",
    "lwncnss3api.cc",
    "lw23412gaapi.cc",
]

# 运行时缓存
_state = {"domains": list(BACKUP), "base": "", "token": ""}


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _headers():
    return {
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/x-www-form-urlencoded",
    }


async def _raw(url, method="GET", data=None):
    opts = {"method": method, "headers": _headers(), "timeout": 12}
    if data is not None:
        opts["body"] = data if isinstance(data, str) else urlencode(data)
        opts["method"] = "POST"
    res = await OmniBox.request(url, opts)
    body = res.get("body") or ""
    return res.get("statusCode") or 0, body


async def _refresh_domains():
    try:
        st, body = await _raw(DOMAIN_API)
        if st == 200 and body:
            try:
                data = json.loads(body)
            except Exception:
                data = {}
            domains = data.get("data") or []
            if isinstance(domains, str):
                try:
                    domains = json.loads(domains)
                except Exception:
                    domains = re.findall(
                        r"[\w\-.]+\.(?:com|cc|net|org|site|top|xyz)", body
                    )
            black = data.get("blackdomain") or []
            if not isinstance(domains, list):
                domains = [domains] if domains else []
            if not isinstance(black, list):
                black = []
            all_d = []
            for d in list(domains) + list(black) + BACKUP:
                d = str(d).strip().replace("https://", "").replace("http://", "").strip("/")
                if d and "." in d and d not in all_d:
                    all_d.append(d)
            if all_d:
                _state["domains"] = all_d
    except Exception as e:
        await OmniBox.log("warn", "[domain] %s" % e)


async def _ensure_base():
    if _state["base"]:
        return _state["base"]
    if not _state["domains"]:
        await _refresh_domains()
    for d in _state["domains"]:
        for proto in ("https", "http"):
            url = "%s://%s/api/setapp.php" % (proto, d)
            try:
                st, body = await _raw(url)
                if st == 200 and body and ("vodtab" in body or "code" in body or "data" in body):
                    _state["base"] = "%s://%s" % (proto, d)
                    await OmniBox.log("info", "[base] %s" % _state["base"])
                    return _state["base"]
            except Exception:
                continue
    _state["base"] = "https://%s" % BACKUP[0]
    return _state["base"]


async def _api(path, method="GET", data=None, retry=True):
    base = await _ensure_base()
    url = base.rstrip("/") + path
    try:
        st, body = await _raw(url, method, data)
        if st == 200 and body:
            try:
                return json.loads(body)
            except Exception:
                pass
    except Exception as e:
        await OmniBox.log("warn", "[api] %s %s" % (path, e))
    if retry:
        _state["base"] = ""
        if base in _state["domains"]:
            d = base.split("://", 1)[-1]
            if d in _state["domains"]:
                _state["domains"].remove(d)
                _state["domains"].append(d)
        return await _api(path, method, data, retry=False)
    return {}


async def _register():
    if _state["token"]:
        return
    data = await _api(
        "/api/newreg.php",
        "POST",
        {"device": "android", "ntoken": "", "channel_code": "vbtQg9D8"},
    )
    token = ((data.get("user") or {}).get("token")) or data.get("token") or ""
    if token:
        _state["token"] = token
        await OmniBox.log("info", "[reg] ok")
    else:
        await OmniBox.log("warn", "[reg] %s" % (data.get("msg") or "no token"))


async def home(params, context):
    try:
        await _register()
        data = await _api("/api/setapp.php", "GET")
        classes = []
        filters = {}
        res_data = data.get("data") if isinstance(data.get("data"), dict) else data
        tabs = (res_data.get("vodtab") or []) + (res_data.get("vodtaban") or [])
        for tab in tabs:
            tid = str(tab.get("type_id") or tab.get("id") or "")
            name = str(tab.get("type_name") or tab.get("name") or tid)
            if not tid:
                continue
            classes.append({"type_id": tid, "type_name": name})
            tags = tab.get("vodtags") or tab.get("tags") or []
            if tags:
                vals = [{"n": "全部", "v": ""}]
                for tg in tags:
                    n = tg.get("name") or tg if isinstance(tg, str) else ""
                    if n:
                        vals.append({"n": n, "v": n})
                filters[tid] = [{"key": "class", "name": "标签", "value": vals}]
        
        items = []
        if classes:
            lst = await category(
                {"categoryId": classes[0]["type_id"], "page": 1}, context
            )
            items = (lst or {}).get("list") or []
        return {"class": classes, "list": items[:30], "filters": filters}
    except Exception as e:
        await OmniBox.log("error", "[home] %s" % e)
        return {"class": [], "list": [], "filters": {}}


async def category(params, context):
    p = params or {}
    tid = str(p.get("categoryId") or p.get("tid") or "")
    page = _to_int(p.get("page"), 1) or 1
    cls = ""
    if isinstance(p.get("filters"), dict):
        cls = str(p["filters"].get("class") or "")
    cls = cls or str(p.get("class") or "")
    if not tid:
        return {"list": [], "page": 1, "pagecount": 0, "limit": 30, "total": 0}
    await _register()
    num = (page - 1) * 30
    payload = {
        "num": str(num),
        "pid": str(tid),
        "area": "全部",
        "vodclass": cls,
        "vodyear": "全部",
        "sort": "1",
        "token": _state.get("token") or "",
    }
    try:
        data = await _api("/api/vlist.php", "POST", payload)
        lst_data = data.get("list") or data.get("data") or []
        videos = []
        for item in lst_data:
            videos.append(
                {
                    "vod_id": str(item.get("vod_id") or item.get("id") or ""),
                    "vod_name": item.get("vod_name") or item.get("name") or "",
                    "vod_pic": item.get("vod_pic") or item.get("pic") or "",
                    "vod_remarks": item.get("vod_class")
                    or item.get("vod_remarks")
                    or item.get("vod_total_time")
                    or "",
                }
            )
        pagecount = page + (1 if len(videos) >= 25 else 0)
        return {
            "list": videos,
            "page": page,
            "pagecount": max(pagecount, page),
            "limit": 30,
            "total": pagecount * 30,
        }
    except Exception as e:
        await OmniBox.log("error", "[category] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "limit": 30, "total": 0}


async def detail(params, context):
    vid = str(
        (params or {}).get("videoId")
        or (params or {}).get("id")
        or (params or {}).get("vod_id")
        or ""
    ).strip()
    if not vid:
        return {"list": []}
    await _register()
    payload = {"id": vid, "token": _state.get("token") or "", "channel": ""}
    try:
        data = await _api("/api/Get_vod_list.php", "POST", payload)
        info = data.get("data") or data
        if not isinstance(info, dict):
            return {"list": []}
        play_url = info.get("vod_play_url") or info.get("play_url") or ""
        if not play_url:
            prev = info.get("preview_url") or ""
            if prev:
                play_url = "预览$%s" % prev
        
        sources = []
        if play_url:
            lines = play_url.split("$$$") if "$$$" in play_url else [play_url]
            for i, line in enumerate(lines):
                eps = []
                for ep in line.split("#"):
                    if not ep.strip():
                        continue
                    if "$" in ep:
                        name, url = ep.split("$", 1)
                    else:
                        name, url = "正片", ep
                    name = name.strip() or "正片"
                    url = url.strip()
                    if url:
                        eps.append({"name": name, "playId": url})
                if eps:
                    sources.append({"name": "线路%s" % (i + 1), "episodes": eps})
        if not sources:
            sources = [{"name": "默认", "episodes": [{"name": "正片", "playId": ""}]}]

        vod = {
            "vod_id": str(info.get("vod_id") or info.get("id") or vid),
            "vod_name": info.get("vod_name") or info.get("name") or vid,
            "vod_pic": info.get("vod_pic") or info.get("pic") or "",
            "vod_remarks": info.get("vod_remarks") or "",
            "vod_content": info.get("vod_blurb") or info.get("vod_content") or "",
            "vod_play_sources": sources,
        }
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", "[detail] %s" % e)
        return {"list": []}


async def search(params, context):
    return {"list": [], "page": 1, "pagecount": 0}


async def play(params, context):
    url = str(
        (params or {}).get("playId")
        or (params or {}).get("url")
        or (params or {}).get("id")
        or ""
    ).strip()
    headers = {"User-Agent": UA}
    if not url:
        return {"urls": [], "parse": 0, "header": headers}
    if url.startswith("http"):
        return {"urls": [{"name": "播放", "url": url}], "parse": 0, "header": headers}
    return {"urls": [], "parse": 0, "header": headers}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})