# -*- coding: utf-8 -*-
# @name 玉女百科
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/Silent1566/OmniBox-Spider/main/影视/采集/玉女百科.py
# @indexs 1
# @description 玉女百科站源（OmniBox 适配版）：HTML 直出 CMS

"""
站点: https://cqglgo.ynbk6.mom
原 T3 接口已统一为 OmniBox handler (params, context)
"""

import re
from urllib.parse import quote

from spider_runner import OmniBox, run

SITE_URL = "https://cqglgo.ynbk6.mom"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

CLASSES = [
    {"type_id": "21", "type_name": "女神学生"},
    {"type_id": "22", "type_name": "美女直播"},
    {"type_id": "23", "type_name": "人妻系列"},
    {"type_id": "24", "type_name": "强奸乱伦"},
    {"type_id": "25", "type_name": "自拍偷拍"},
    {"type_id": "26", "type_name": "制服诱惑"},
    {"type_id": "27", "type_name": "巨乳系列"},
    {"type_id": "28", "type_name": "自慰系列"},
    {"type_id": "29", "type_name": "国产视频"},
    {"type_id": "30", "type_name": "无码视频"},
    {"type_id": "31", "type_name": "有码视频"},
    {"type_id": "32", "type_name": "中文字幕"},
    {"type_id": "33", "type_name": "日韩精品"},
    {"type_id": "34", "type_name": "欧美精品"},
    {"type_id": "35", "type_name": "动漫精品"},
    {"type_id": "36", "type_name": "三级伦理"},
]


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _is_minor(text):
    if not text:
        return False
    t = text.lower()
    for kw in ["萝莉", "幼女", "少女", "loli", "teen", "schoolgirl", "童颜", "小学生", "初中生", "高中生", "jk", "女子校生", "18岁以下", "未成年"]:
        if kw in t:
            return True
    return False


async def _fetch(url):
    res = await OmniBox.request(
        url,
        {
            "method": "GET",
            "headers": {
                "User-Agent": UA,
                "Referer": SITE_URL + "/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            "timeout": 15,
        },
    )
    if (res.get("statusCode") or 0) != 200:
        return ""
    return res.get("body") or ""


def _parse_list(html):
    results = []
    pattern = re.compile(
        r'<a[^>]*class="videoBox"[^>]*href="/(\d+)\.html"[^>]*>(.*?)</a>\s*<div[^>]*class="videoBox-actor"[^>]*>(.*?)</div>',
        re.DOTALL,
    )
    for m in pattern.finditer(html or ""):
        vid = m.group(1)
        inner = m.group(2)
        pic = ""
        pm = re.search(r'data-src="([^"]+)"', inner)
        if pm:
            pic = pm.group(1)
        title = ""
        tm = re.search(r'<h4[^>]*class="title"[^>]*>([^<]+)</h4>', inner)
        if tm:
            title = tm.group(1).strip()
        remark = ""
        dm = re.search(r'<div[^>]*class="videoBox-time"[^>]*>([^<]*)</div>', inner)
        if dm:
            remark = dm.group(1).strip()
        if _is_minor(title):
            continue
        results.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": remark})
    return results


def _parse_page_info(html, base_url):
    page = 1
    pagecount = 1
    pm = re.search(r"-(\d+)\.html", base_url or "")
    if pm:
        page = int(pm.group(1))
    lm = re.search(r"/vodtype/\d+-(\d+)\.html[^>]*>尾页", html or "")
    if lm:
        pagecount = int(lm.group(1))
    else:
        lm2 = re.search(r"/s/[^\"']+-(\d+)\.html[^>]*>尾页", html or "")
        if lm2:
            pagecount = int(lm2.group(1))
    return page, pagecount


async def home(params, context):
    try:
        await OmniBox.log("info", f"[home] from={(context or {}).get('from', 'web')}")
        html = await _fetch(SITE_URL + "/ynbk/")
        return {"class": CLASSES, "list": _parse_list(html), "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] 失败: {e}")
        return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    try:
        tid = str((params or {}).get("categoryId") or "21")
        page = _to_int((params or {}).get("page"), 1) or 1
        await OmniBox.log("info", f"[category] categoryId={tid}, page={page}")
        if page <= 1:
            url = f"{SITE_URL}/vodtype/{tid}.html"
        else:
            url = f"{SITE_URL}/vodtype/{tid}-{page}.html"
        html = await _fetch(url)
        lst = _parse_list(html)
        _, pagecount = _parse_page_info(html, url)
        return {
            "list": lst,
            "page": page,
            "pagecount": max(1, pagecount),
            "limit": 20,
            "total": max(1, pagecount) * 20,
        }
    except Exception as e:
        await OmniBox.log("error", f"[category] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 20}


async def detail(params, context):
    try:
        vid = str((params or {}).get("videoId") or "")
        if not vid:
            return {"list": []}
        await OmniBox.log("info", f"[detail] videoId={vid}")
        html = await _fetch(f"{SITE_URL}/{vid}.html")
        title = ""
        tm = re.search(
            r'<h1[^>]*class="video-title"[^>]*>.*?<span[^>]*class="title"[^>]*>([^<]+)</span>',
            html or "",
            re.DOTALL,
        )
        if tm:
            title = tm.group(1).strip()
        pic = ""
        pm = re.search(r'property="og:image"\s+content="([^"]+)"', html or "")
        if pm:
            pic = pm.group(1)
        type_name = ""
        cm = re.search(r'<span[^>]*class="cates"[^>]*>.*?<a[^>]*>([^<]+)</a>', html or "", re.DOTALL)
        if cm:
            type_name = cm.group(1).strip()
        m3u8 = ""
        mm = re.search(r"const\s+rawUrl\s*=\s*'([^']+)'", html or "")
        if mm:
            m3u8 = mm.group(1)
        desc = ""
        dm = re.search(r'property="og:description"\s+content="([^"]+)"', html or "")
        if dm:
            desc = dm.group(1)
        vod = {
            "vod_id": vid,
            "vod_name": title or vid,
            "vod_pic": pic,
            "vod_remarks": type_name,
            "vod_content": desc,
        }
        if m3u8:
            vod["vod_play_sources"] = [{"name": "玉女百科", "episodes": [{"name": "正片", "playId": m3u8}]}]
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] 失败: {e}")
        return {"list": []}


async def search(params, context):
    try:
        wd = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not wd:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 20}
        await OmniBox.log("info", f"[search] keyword={wd}, page={page}")
        enc = quote(wd)
        url = f"{SITE_URL}/s/{enc}.html" if page <= 1 else f"{SITE_URL}/s/{enc}-{page}.html"
        html = await _fetch(url)
        lst = _parse_list(html)
        _, pagecount = _parse_page_info(html, url)
        return {
            "list": lst,
            "page": page,
            "pagecount": max(1, pagecount),
            "limit": 20,
            "total": max(1, pagecount) * 20,
        }
    except Exception as e:
        await OmniBox.log("error", f"[search] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 20}


async def play(params, context):
    try:
        play_id = str((params or {}).get("playId") or "")
        flag = str((params or {}).get("flag") or "play")
        if not play_id:
            raise ValueError("playId 为空")
        url = play_id
        if not url.startswith("http"):
            html = await _fetch(f"{SITE_URL}/{url}.html")
            mm = re.search(r"const\s+rawUrl\s*=\s*'([^']+)'", html or "")
            if mm:
                url = mm.group(1)
        parse = 0 if any(x in url.lower() for x in (".m3u8", ".mp4")) else 1
        await OmniBox.log("info", f"[play] playId={url[:80]}, parse={parse}")
        return {
            "urls": [{"name": "播放", "url": url}] if url else [],
            "flag": flag,
            "header": {"User-Agent": UA, "Referer": SITE_URL + "/"},
            "parse": parse,
        }
    except Exception as e:
        await OmniBox.log("error", f"[play] 失败: {e}")
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
