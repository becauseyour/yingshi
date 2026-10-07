# -*- coding: utf-8 -*-
# @name 淫花宫
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/Silent1566/OmniBox-Spider/main/影视/采集/淫花宫.py
# @indexs 1
# @description 淫花宫站源（OmniBox 适配版）：苹果CMS 结构，HTML 直出

"""
站点: https://breplc.yhg5.help
原 T3 接口已统一为 OmniBox handler (params, context)
"""

import re
from urllib.parse import quote

from spider_runner import OmniBox, run

SITE_URL = "https://breplc.yhg5.help"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

CLASSES = [
    {"type_name": "熟母少妇", "type_id": "20"},
    {"type_name": "网红直播", "type_id": "21"},
    {"type_name": "自拍偷拍", "type_id": "22"},
    {"type_name": "强奸乱伦", "type_id": "23"},
    {"type_name": "高清国产", "type_id": "24"},
    {"type_name": "韩国专区", "type_id": "25"},
    {"type_name": "日本有码", "type_id": "26"},
    {"type_name": "日本无码", "type_id": "27"},
    {"type_name": "欧美情色", "type_id": "28"},
    {"type_name": "动漫卡通", "type_id": "29"},
    {"type_name": "三级伦理", "type_id": "30"},
]


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


async def _fetch(url):
    res = await OmniBox.request(
        url,
        {"method": "GET", "headers": {"User-Agent": UA, "Referer": SITE_URL + "/"}, "timeout": 15},
    )
    if (res.get("statusCode") or 0) != 200:
        return ""
    return res.get("body") or ""


def _parse_list(html, limit=0):
    videos = []
    link_items = re.findall(r'<a[^>]*href="/(\d+\.html)"[^>]*title="([^"]*)"', html or "", re.S)
    img_items = re.findall(r'<img[^>]*(?:data-original|src)="([^"]*)"', html or "", re.S)
    for i, (url, title) in enumerate(link_items):
        vid = re.search(r"(\d+)\.html", url)
        if not vid:
            continue
        img = img_items[i] if i < len(img_items) else ""
        videos.append({
            "vod_id": vid.group(1),
            "vod_name": title,
            "vod_pic": img,
            "vod_remarks": "",
        })
        if limit and len(videos) >= limit:
            break
    return videos


async def home(params, context):
    try:
        await OmniBox.log("info", f"[home] from={(context or {}).get('from', 'web')}")
        html = await _fetch(SITE_URL + "/cn/home/web/")
        return {"class": CLASSES, "list": _parse_list(html, limit=20), "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] 失败: {e}")
        return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    try:
        tid = str((params or {}).get("categoryId") or "20")
        page = _to_int((params or {}).get("page"), 1) or 1
        await OmniBox.log("info", f"[category] categoryId={tid}, page={page}")
        url = f"{SITE_URL}/vodtype/{tid}.html"
        if page > 1:
            url = f"{SITE_URL}/vodtype/{tid}/page/{page}.html"
        html = await _fetch(url)
        videos = _parse_list(html)
        return {
            "list": videos,
            "page": page,
            "pagecount": 100,
            "limit": 30,
            "total": 3000,
        }
    except Exception as e:
        await OmniBox.log("error", f"[category] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 30}


async def detail(params, context):
    try:
        vid = str((params or {}).get("videoId") or "")
        if not vid:
            return {"list": []}
        await OmniBox.log("info", f"[detail] videoId={vid}")
        html = await _fetch(f"{SITE_URL}/{vid}.html")
        title_m = re.search(r"<title>([^<]*)</title>", html or "")
        title = title_m.group(1).split("_")[0] if title_m else vid
        m3u8_m = re.search(r"['\"]([^'\"]*\.m3u8[^'\"]*)['\"]", html or "")
        m3u8_url = (m3u8_m.group(1).replace("\\/", "/") if m3u8_m else "")
        episodes = [{"name": "正片", "playId": m3u8_url}] if m3u8_url else []
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": "",
            "vod_remarks": "",
            "vod_content": "",
        }
        if episodes:
            vod["vod_play_sources"] = [{"name": "直链", "episodes": episodes}]
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] 失败: {e}")
        return {"list": []}


async def search(params, context):
    try:
        key = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 30}
        await OmniBox.log("info", f"[search] keyword={key}")
        html = await _fetch(f"{SITE_URL}/s/{quote(key)}.html")
        items = re.findall(
            r'<a[^>]*href="/(\d+\.html)"[^>]*title="([^"]*)"[^>]*>.*?<img[^>]*(?:data-original|src)="([^"]*)"',
            html or "",
            re.S,
        )
        videos = []
        for url, title, img in items:
            vid = re.search(r"(\d+)\.html", url)
            if vid:
                videos.append({
                    "vod_id": vid.group(1),
                    "vod_name": title,
                    "vod_pic": img,
                    "vod_remarks": "",
                })
        return {"list": videos, "page": 1, "pagecount": 1, "limit": 30, "total": len(videos)}
    except Exception as e:
        await OmniBox.log("error", f"[search] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 30}


async def play(params, context):
    try:
        play_id = str((params or {}).get("playId") or "")
        flag = str((params or {}).get("flag") or "play")
        if not play_id:
            raise ValueError("playId 为空")
        parse = 0 if ".m3u8" in play_id.lower() or ".mp4" in play_id.lower() else 1
        await OmniBox.log("info", f"[play] playId={play_id[:80]}, parse={parse}")
        return {
            "urls": [{"name": "播放", "url": play_id}],
            "flag": flag,
            "header": {"User-Agent": UA, "Referer": SITE_URL + "/"},
            "parse": parse,
        }
    except Exception as e:
        await OmniBox.log("error", f"[play] 失败: {e}")
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
