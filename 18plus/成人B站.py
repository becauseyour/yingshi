# -*- coding: utf-8 -*-
# @name 成人B站
# @version 1.2.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/%E6%88%90%E4%BA%BAB%E7%AB%99.py
# @description 成人B站（MacCMS API，OmniBox）

"""
成人B站 v1.1.0
API: https://fqzy.me/api.php/provide/vod

适配说明（相对 v1.1.1）：
- API 域名多源回退：fqzy.me → fqzy.cc（实测 fanqiezy.com 已停放
  弃用），任一域名返回有效数据即记住该域名，全部失败才返回空
  （应对单域名被墙/DNS 污染导致列表为空）；
- v1.1.1 已修复 OmniBox.request 调用签名（第二参数传选项字典，
  响应用 res.get("body")/res.get("statusCode") 读取）；
- 其余适配点同前：参数名对齐框架约定、搜索 videolist/list 双
  回退、无已移除 SDK 调用、播放直出直链、无索引声明行。
"""

import json
import re
from urllib.parse import quote

from spider_runner import OmniBox, run

HOSTS = ["fqzy.me", "fqzy.cc"]
_HOST = HOSTS[0]

def _api(query):
    return f"https://{_HOST}/api.php/provide/vod/?{query}"
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


def _page(value, default=1):
    try:
        page = int(value)
        return page if page >= 1 else default
    except (TypeError, ValueError):
        return default


async def _fetch(query):
    """按域名顺序请求 API，成功即记住该域名；全部失败返回 {}"""
    global _HOST
    last_err = ""
    for host in HOSTS:
        _HOST = host
        try:
            res = await OmniBox.request(
                _api(query),
                {
                    "method": "GET",
                    "headers": {"User-Agent": UA, "Accept": "application/json"},
                    "timeout": 12,
                },
            )
            code = (res or {}).get("statusCode")
            if code not in (None, 0, 200):
                last_err = f"HTTP {code}"
                await OmniBox.log("error", f"[成人B站] {host} {last_err}")
                continue
            body = (res or {}).get("body") or ""
            if isinstance(body, str):
                try:
                    data = json.loads(body)
                except Exception:
                    last_err = "json decode failed"
                    continue
            else:
                data = body
            if isinstance(data, dict) and data.get("list") is not None:
                return data
            last_err = "unexpected payload"
        except Exception as e:
            last_err = str(e)
            await OmniBox.log("error", f"[成人B站] {host} request failed: {e}")
    await OmniBox.log("error", f"[成人B站] all hosts failed, last={last_err}")
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
        "vod_year": str(v.get("vod_year") or "").strip(),
        "type_name": str(v.get("type_name") or "").strip(),
    }


def _normalize_list(items):
    return [_item(x) for x in items or [] if x.get("vod_id")]


async def home(params, context):
    return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    try:
        p = params or {}
        # 框架约定主传 categoryId，兼容旧的 type_id/tid 写法
        tid = str(p.get("categoryId") or p.get("type_id") or p.get("tid") or "7")
        page = _page(p.get("page"))
        data = await _fetch(f"ac=videolist&t={tid}&pg={page}")
        items = data.get("list") or []
        list_ = _normalize_list(items)
        pagecount = _page(data.get("pagecount"), 1)
        total = _page(data.get("total"), len(list_))
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
        keyword = str(p.get("keyword") or p.get("wd") or p.get("key") or "").strip()
        page = _page(p.get("page"))
        if not keyword:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        # 兼容部分 MacCMS 站点只支持 ac=list 搜索：videolist 无结果时回退一次
        data = await _fetch(f"ac=videolist&wd={quote(keyword)}&pg={page}")
        list_ = _normalize_list(data.get("list"))
        if not list_:
            data = await _fetch(f"ac=list&wd={quote(keyword)}&pg={page}")
            list_ = _normalize_list(data.get("list"))
        pagecount = _page(data.get("pagecount"), 1)
        return {
            "list": list_,
            "page": page,
            "pagecount": pagecount,
            "total": _page(data.get("total"), len(list_)),
        }
    except Exception as e:
        await OmniBox.log("error", f"[search] {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}


async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or p.get("vod_id") or "").split("@@")[0].strip()
        if not vid:
            return {"list": []}
        data = await _fetch(f"ac=detail&ids={vid}")
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
            return {"list": []}

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
        flag = str(p.get("flag") or "")
        headers = {"User-Agent": UA, "Referer": "https://fqzy.me/"}
        if not play_id:
            return {"urls": [], "parse": 0, "header": headers}
        # 直接返回 m3u8/mp4/flv 直链，无需解析
        parse = 0 if re.search(r"\.(m3u8|mp4|flv)", play_id, re.I) else 1
        await OmniBox.log("info", f"[play] flag={flag} parse={parse}")
        return {
            "urls": [{"name": "播放", "url": play_id}],
            "parse": parse,
            "header": headers,
        }
    except Exception as e:
        await OmniBox.log("error", f"[play] {e}")
        return {"urls": [], "parse": 0, "header": {}}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
