# -*- coding: utf-8 -*-
# @name 成人B站
# @version 1.0.3
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/%E6%88%90%E4%BA%BAB%E7%AB%99.py
# @description 成人B站（MacCMS API，OmniBox）

import json
import re
from urllib.parse import quote
from spider_runner import OmniBox, run

API = "https://fqzy.me/api.php/provide/vod"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

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

async def _get_json(url):
    try:
        res = await OmniBox.request(url, method="GET", headers={"User-Agent": UA, "Accept": "application/json,text/plain,*/*"})
        body = getattr(res, "body", None)
        if body is None:
            body = getattr(res, "text", None) or getattr(res, "data", None)
        if isinstance(body, (dict, list)):
            return body if isinstance(body, dict) else {"list": body}
        if isinstance(body, str):
            body = body.strip()
            if body.startswith("{") or body.startswith("["):
                return json.loads(body)
        await OmniBox.log("warn", f"[成人B站] unexpected body type: {type(body)}")
        return {}
    except Exception as e:
        await OmniBox.log("error", f"[成人B站] request failed: {e}")
        return {}

def _item(v, cat_name=""):
    vid = str(v.get("vod_id") or "")
    name = (v.get("vod_name") or "").strip()
    pic = (v.get("vod_pic") or "").strip()
    remarks = (v.get("vod_remarks") or v.get("type_name") or "").strip()
    if cat_name:
        remarks = f"[{cat_name}] {remarks}".strip()
    return {"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": remarks}

async def home(params, context):
    try:
        await OmniBox.log("info", "[home] start")
        list_ = []
        data = await _get_json(f"{API}/?ac=videolist&pg=1")
        for x in (data.get("list") or [])[:12]:
            if x.get("vod_id"):
                list_.append(_item(x, "最新"))
        for c in CLASSES[:4]:
            data = await _get_json(f"{API}/?ac=videolist&t={c['type_id']}&pg=1")
            for x in (data.get("list") or [])[:6]:
                if x.get("vod_id"):
                    list_.append(_item(x, c["type_name"]))
        await OmniBox.log("info", f"[home] got {len(list_)} items")
        return {"class": CLASSES, "list": list_, "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] {e}")
        return {"class": CLASSES, "list": [], "filters": {}}

async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("type_id") or p.get("tid") or "7")
        page = int(p.get("page") or 1)
        await OmniBox.log("info", f"[category] tid={tid} page={page}")
        url = f"{API}/?ac=videolist&t={tid}&pg={page}"
        data = await _get_json(url)
        items = data.get("list") or []
        list_ = [_item(x) for x in items if x.get("vod_id")]
        pagecount = int(data.get("pagecount") or 1)
        total = int(data.get("total") or len(list_))
        return {"list": list_, "page": page, "pagecount": pagecount, "total": total, "limit": 20}
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
        data = await _get_json(url)
        items = data.get("list") or []
        list_ = [_item(x) for x in items if x.get("vod_id")]
        pagecount = int(data.get("pagecount") or 1)
        return {"list": list_, "page": page, "pagecount": pagecount, "total": int(data.get("total") or len(list_))}
    except Exception as e:
        await OmniBox.log("error", f"[search] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}

async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or p.get("vod_id") or "").split("@@")[0]
        if not vid:
            return {"list": []}
        data = await _get_json(f"{API}/?ac=detail&ids={vid}")
        items = data.get("list") or []
        if not items:
            return {"list": []}
        v = items[0]
        play_url = v.get("vod_play_url") or ""
        sources = []
        if play_url:
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
        return {"list": [{"vod_id": vid, "vod_name": v.get("vod_name") or vid, "vod_pic": v.get("vod_pic") or "", "vod_content": v.get("vod_content") or "", "vod_remarks": v.get("vod_remarks") or v.get("type_name") or "", "vod_play_sources": sources}]}
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
        if re.search(r"\.(m3u8|mp4|flv)", play_id, re.I):
            return {"urls": [{"name": "播放", "url": play_id}], "parse": 0, "header": headers}
        return {"urls": [{"name": "播放", "url": play_id}], "parse": 1, "header": headers}
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}

if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
