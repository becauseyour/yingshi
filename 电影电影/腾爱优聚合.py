# -*- coding: utf-8 -*-
# @name 腾爱优聚合
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%94%B5%E5%BD%B1%E7%94%B5%E8%A7%86/%E8%85%BE%E7%88%B1%E4%BC%98%E8%81%9A%E5%90%88.py
# @description 腾讯/爱奇艺/优酷/芒果/B站 聚合（OmniBox）

"""
腾爱优聚合 v1.0.0
采集: http://cj.tianwe.cn
播放: 官站链接 parse=1（客户端解析）
"""

import json
import re
from urllib.parse import quote

from spider_runner import OmniBox, run

HOST = "http://cj.tianwe.cn"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 数字 id -> 接口 from 参数
_CATEGORY = {
    "1": ("qq", "腾讯视频"),
    "2": ("qiyi", "爱奇艺"),
    "3": ("youku", "优酷视频"),
    "4": ("mgtv", "芒果TV"),
    "5": ("bilibili", "B站"),
}


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _to_key(tid):
    s = str(tid or "").strip()
    if s in _CATEGORY:
        return _CATEGORY[s][0]
    return s or "qq"


def _is_media(url):
    u = str(url or "")
    return bool(re.search(r"\.(m3u8|mp4)(\?|$)", u, re.I))


async def _get_json(url):
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
        raise RuntimeError("HTTP %s" % (res.get("statusCode"),))
    return json.loads(body)


def _card(v):
    return {
        "vod_id": str(v.get("vod_id") or ""),
        "vod_name": str(v.get("vod_name") or "").strip(),
        "vod_pic": str(v.get("vod_pic") or ""),
        "vod_remarks": str(v.get("vod_remarks") or ""),
    }


def _play_sources(play_from, play_url):
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
            else:
                ep_name, pid = "第%s集" % (j + 1), seg
            ep_name, pid = ep_name.strip(), pid.strip()
            if pid:
                eps.append({"name": ep_name or ("第%s集" % (j + 1)), "playId": pid})
        if eps:
            sources.append({"name": name, "episodes": eps})
    return sources


async def home(params, context):
    try:
        classes = [
            {"type_id": k, "type_name": v[1]} for k, v in _CATEGORY.items()
        ]
        type_filter = {
            "key": "class",
            "name": "类型",
            "value": [
                {"n": "全部", "v": ""},
                {"n": "电视剧", "v": "2"},
                {"n": "电影", "v": "1"},
                {"n": "动漫", "v": "4"},
                {"n": "综艺", "v": "3"},
                {"n": "少儿", "v": "5"},
                {"n": "纪录片", "v": "6"},
                {"n": "短剧", "v": "7"},
            ],
        }
        year_filter = {
            "key": "year",
            "name": "年份",
            "value": [{"n": "全部", "v": ""}]
            + [{"n": str(y), "v": str(y)} for y in range(2026, 2019, -1)],
        }
        filters = {k: [type_filter, year_filter] for k in _CATEGORY}
        return {"class": classes, "list": [], "filters": filters}
    except Exception as e:
        await OmniBox.log("error", "[home] %s" % e)
        return {"class": [], "list": [], "filters": {}}


async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("tid") or "1")
        page = _to_int(p.get("page"), 1) or 1
        extend = p.get("filters") or p.get("extend") or {}
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}

        key = _to_key(tid)
        t = str(extend.get("class") or "2")
        qs = [
            "from=" + key,
            "ac=detail",
            "limit=24",
            "pg=" + str(page),
            "t=" + t,
        ]
        if extend.get("year"):
            qs.append("year=" + quote(str(extend["year"])))
        url = HOST + "/api.php/provide/vod/?" + "&".join(qs)
        await OmniBox.log("info", "[category] %s" % url)
        data = await _get_json(url)
        items = [_card(v) for v in (data.get("list") or []) if v.get("vod_id")]
        pc = _to_int(data.get("pagecount"), 1) or 1
        return {
            "list": items,
            "page": page,
            "pagecount": pc,
            "limit": 24,
            "total": _to_int(data.get("total"), pc * len(items)),
        }
    except Exception as e:
        await OmniBox.log("error", "[category] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "limit": 24, "total": 0}


async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or p.get("vod_id") or "").strip()
        vid = vid.split("$")[-1].strip()
        if not vid:
            return {"list": []}
        url = HOST + "/api.php/provide/vod/?ac=detail&ids=" + quote(vid)
        data = await _get_json(url)
        item = (data.get("list") or [None])[0]
        if not item:
            return {"list": []}
        sources = _play_sources(item.get("vod_play_from"), item.get("vod_play_url"))
        vod = {
            "vod_id": str(item.get("vod_id") or vid),
            "vod_name": str(item.get("vod_name") or "").strip(),
            "vod_pic": str(item.get("vod_pic") or ""),
            "vod_year": str(item.get("vod_year") or ""),
            "vod_area": str(item.get("vod_area") or ""),
            "vod_remarks": str(item.get("vod_remarks") or ""),
            "type_name": str(item.get("type_name") or ""),
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
        url = (
            HOST
            + "/api.php/provide/vod/?ac=detail&wd="
            + quote(key)
            + "&pg="
            + str(page)
        )
        data = await _get_json(url)
        items = [_card(v) for v in (data.get("list") or []) if v.get("vod_id")]
        return {
            "list": items,
            "page": page,
            "pagecount": _to_int(data.get("pagecount"), 1) or 1,
            "total": _to_int(data.get("total"), 0),
        }
    except Exception as e:
        await OmniBox.log("error", "[search] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}


async def play(params, context):
    try:
        p = params or {}
        play_id = str(p.get("playId") or p.get("url") or "").strip()
        headers = {"User-Agent": UA}
        if not play_id:
            return {"urls": [], "parse": 0, "header": headers}
        if _is_media(play_id):
            return {
                "urls": [{"name": "播放", "url": play_id}],
                "parse": 0,
                "header": headers,
            }
        # 官站链接交给客户端解析
        return {
            "urls": [{"name": "播放", "url": play_id}],
            "parse": 1,
            "header": headers,
            "jx": play_id,
        }
    except Exception as e:
        await OmniBox.log("error", "[play] %s" % e)
        return {"urls": [], "parse": 0, "header": {}}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
