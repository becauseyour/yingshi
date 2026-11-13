# -*- coding: utf-8 -*-
# @name 成人B站
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/%E6%88%90%E4%BA%BAB%E7%AB%99.py
# @description 成人B站（MacCMS API，OmniBox）

"""
成人B站 v1.0.0
API: https://fqzy.me/api.php/provide/vod
"""

import json
import re
from urllib.parse import quote

from spider_runner import OmniBox, run

API = "https://fqzy.me/api.php/provide/vod"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

CLASSES = [
    {"type_id": "7", "type_name": "国产大制作"},
    {"type_id": "6", "type_name": "偷拍自拍"},
    {"type_id": "10", "type_name": "黑料网曝"},
    {"type_id": "29", "type_name": "会所技师"},
    {"type_id": "31", "type_name": "探花约炮"},
    {"type_id": "30", "type_name": "国产推荐"},
    {"type_id": "33", "type_name": "国产直播"},
    {"type_id": "34", "type_name": "淫妻绿帽"},
    {"type_id": "35", "type_name": "制服诱惑"},
    {"type_id": "8", "type_name": "乱伦毁三观"},
    {"type_id": "9", "type_name": "主播女网红"},
    {"type_id": "21", "type_name": "淫乱学生妹"},
    {"type_id": "3", "type_name": "欧美精品"},
    {"type_id": "13", "type_name": "高清无码"},
    {"type_id": "14", "type_name": "中文字幕"},
    {"type_id": "24", "type_name": "高清有码"},
    {"type_id": "27", "type_name": "无码流出"},
    {"type_id": "28", "type_name": "FC2"},
    {"type_id": "22", "type_name": "动漫精选"},
    {"type_id": "32", "type_name": "韩国直播"},
    {"type_id": "36", "type_name": "重口猎奇"},
    {"type_id": "37", "type_name": "东京热"},
    {"type_id": "38", "type_name": "一本道"},
]


async def _get(url):
    try:
        res = await OmniBox.request(
            url,
            method="GET",
            headers={"User-Agent": UA, "Accept": "application/json"},
        )
        body = res.body
        if isinstance(body, str):
            try:
                return json.loads(body)
            except Exception:
                return {}
        return body or {}
    except Exception as e:
        await OmniBox.log("error", f"[成人B站] request failed: {e}")
        return {}


def _item(v):
    vid = str(v.get("vod_id") or "")
    name = (v.get("vod_name") or "").strip()
    pic = (v.get("vod_pic") or "").strip()
    remarks = (v.get("vod_remarks") or v.get("type_name") or "").strip()
    return {
        "vod_id": vid,
        "vod_name": name,
        "vod_pic": pic,
        "vod_remarks": remarks,
    }


async def home(params, context):
    return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("type_id") or p.get("tid") or "7")
        page = int(p.get("page") or 1)
        url = f"{API}/?ac=videolist&t={tid}&pg={page}"
        data = await _get(url)
        items = data.get("list") or []
        list_ = [_item(x) for x in items if x.get("vod_id")]
        pagecount = int(data.get("pagecount") or 1)
        total = int(data.get("total") or 0)
        return {
            "list": list_,
            "page": page,
            "pagecount": pagecount,
            "total": total,
        }
    except Exception as e:
        await OmniBox.log("error", f"[category] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}


async def search(params, context):
    try:
        p = params or {}
        keyword = (p.get("keyword") or p.get("wd") or "").strip()
        page = int(p.get("page") or 1)
        if not keyword:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        url = f"{API}/?ac=videolist&wd={quote(keyword)}&pg={page}"
        data = await _get(url)
        items = data.get("list") or []
        list_ = [_item(x) for x in items if x.get("vod_id")]
        pagecount = int(data.get("pagecount") or 1)
        return {
            "list": list_,
            "page": page,
            "pagecount": pagecount,
            "total": int(data.get("total") or len(list_)),
        }
    except Exception as e:
        await OmniBox.log("error", f"[search] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}


async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or p.get("vod_id") or "").split("@@")[0]
        if not vid:
            return {"list": []}
        url = f"{API}/?ac=detail&ids={vid}"
        data = await _get(url)
        items = data.get("list") or []
        if not items:
            return {"list": []}
        v = items[0]
        play_url = v.get("vod_play_url") or ""
        # 解析播放地址
        sources = []
        if play_url:
            # MacCMS 格式: 第1集$url#第2集$url$$$源2...
            for group in play_url.split("$$$"):
                eps = []
                for ep in group.split("#"):
                    if "$" in ep:
                        name, u = ep.split("$", 1)
                        if u.startswith("http"):
                            eps.append({"name": name.strip() or "播放", "playId": u})
                if eps:
                    sources.append({"name": "线路", "episodes": eps})
        if not sources:
            sources = [{"name": "默认", "episodes": [{"name": "播放", "playId": ""}]}]

        return {
            "list": [
                {
                    "vod_id": vid,
                    "vod_name": v.get("vod_name") or vid,
                    "vod_pic": v.get("vod_pic") or "",
                    "vod_content": v.get("vod_content") or "",
                    "vod_remarks": v.get("vod_remarks") or v.get("type_name") or "",
                    "vod_play_sources": sources,
                }
            ]
        }
    except Exception as e:
        await OmniBox.log("error", f"[detail] {e}")
        return {"list": []}


async def play(params, context):
    try:
        p = params or {}
        play_id = str(p.get("playId") or p.get("url") or "").strip()
        headers = {"User-Agent": UA, "Referer": "https://fqzy.me/"}
        if not play_id:
            return {"urls": [], "parse": 0, "header": headers}
        # 直接返回 m3u8/mp4
        if re.search(r"\.(m3u8|mp4|flv)", play_id, re.I):
            return {
                "urls": [{"name": "播放", "url": play_id}],
                "parse": 0,
                "header": headers,
            }
        return {
            "urls": [{"name": "播放", "url": play_id}],
            "parse": 1,
            "header": headers,
        }
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
