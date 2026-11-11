# -*- coding: utf-8 -*-
# @name 清纯人妻
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/清纯人妻.py
# @description 清纯人妻 AV 站点（女优/中字/熟女/制服等），直连 m3u8

import re
import html
from urllib.parse import quote, urljoin

from spider_runner import OmniBox, run

HOST = "https://wtwgi.qingwife01.club/qcrq"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": HOST + "/",
}

CLASSES = [
    {"type_name": "女优明星", "type_id": "nv-you-ming-xing"},
    {"type_name": "欧美无码", "type_id": "ou-mei-wu-ma"},
    {"type_name": "中文字幕", "type_id": "zhong-wen-zi-mu"},
    {"type_name": "熟女人妻", "type_id": "shu-nv-ren-qi"},
    {"type_name": "制服诱惑", "type_id": "zhi-fu-you-huo"},
    {"type_name": "多人群交", "type_id": "duo-ren-qun-jiao"},
    {"type_name": "萝莉少女", "type_id": "luo-li-shao-nv"},
    {"type_name": "强奸乱伦", "type_id": "qiang-jian-luan-lun"},
    {"type_name": "网红头条", "type_id": "wang-hong-tou-tiao"},
    {"type_name": "SM调教", "type_id": "SM-tiao-jiao"},
    {"type_name": "国产自拍", "type_id": "guo-chan-zi-pai"},
    {"type_name": "欧美系列", "type_id": "ou-mei-xi-lie"},
    {"type_name": "美女主播", "type_id": "mei-nv-zhu-bo"},
    {"type_name": "抖音视频", "type_id": "dou-yin-shi-pin"},
    {"type_name": "网爆黑料", "type_id": "wang-bao-hei-liao"},
    {"type_name": "卡通动漫", "type_id": "ka-tong-dong-man"},
    {"type_name": "AI换脸", "type_id": "AI-huan-lian"},
    {"type_name": "韩国主播", "type_id": "han-guo-zhu-bo"},
    {"type_name": "麻豆传媒", "type_id": "ma-dou-chuan-mei"},
    {"type_name": "三级伦理", "type_id": "san-ji-lun-li"},
    {"type_name": "AV解说", "type_id": "AV-jie-shuo"},
    {"type_name": "无码专区", "type_id": "wu-ma-zhuan-qu"},
    {"type_name": "美乳巨乳", "type_id": "mei-ru-ju-ru"},
    {"type_name": "女同性爱", "type_id": "nv-tong-xing-ai"},
]


def clean_text(text):
    if not text:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", str(text))).strip()


def fix_url(url):
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(HOST + "/", url)
    if url.startswith("http"):
        return url
    return urljoin(HOST + "/", url)


async def _get(url, timeout=15):
    try:
        res = await OmniBox.request(
            url, {"method": "GET", "headers": HEADERS, "timeout": timeout}
        )
        body = res.get("body") or ""
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="ignore")
        status = int(res.get("statusCode") or 0)
        if status and status >= 400:
            return ""
        return str(body)
    except Exception as e:
        await OmniBox.log("error", "[request] %s %s" % (url, e))
        return ""


def _parse_list(html_text):
    items = []
    seen = set()
    pattern = r'<a[^>]*href=["\']([^"\']*/v/video-(\d+)/)["\'][^>]*>[\s\S]*?<img[^>]*src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\'][^>]*>[\s\S]*?<span>([^<]+)</span>'
    for m in re.finditer(pattern, html_text, re.I):
        href, vid, pic, alt, title = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        if vid in seen:
            continue
        seen.add(vid)
        items.append({"vod_id": vid, "vod_name": clean_text(title or alt), "vod_pic": fix_url(pic), "vod_remarks": ""})
    if items:
        return items
    pattern2 = r'href=["\']([^"\']*/v/video-(\d+)/)["\']'
    for m in re.finditer(pattern2, html_text):
        href, vid = m.group(1), m.group(2)
        if vid in seen:
            continue
        seen.add(vid)
        items.append({"vod_id": vid, "vod_name": "video-" + vid, "vod_pic": "", "vod_remarks": ""})
    return items


def extract_play(html_text):
    m = re.search(r"(https?://\S+?\.m3u8)", html_text)
    if m: return m.group(1)
    m = re.search(r"(https?://\S+?\.mp4)", html_text)
    if m: return m.group(1)
    m = re.search(r'var\s+src\s*=\s*(["\'])(.+?)\1', html_text)
    if m: return m.group(2).replace("\\/", "/")
    m = re.search(r'player_data\s*=\s*(\{.*?\})', html_text, re.S)
    if m:
        try:
            import json
            return json.loads(m.group(1)).get("url", "")
        except Exception:
            pass
    m = re.search(r"(https?://\S+?\.(?:m3u8|mp4|flv))", html_text)
    return m.group(1) if m else ""


async def home(params, context):
    first = CLASSES[0]["type_id"]
    url = f"{HOST}/vtype/{first}/"
    html_text = await _get(url)
    list_items = _parse_list(html_text)[:40] if html_text else []
    return {"class": CLASSES, "list": list_items, "filters": {}}


async def category(params, context):
    p = params or {}
    tid = str(p.get("categoryId") or p.get("tid") or "").strip()
    page = 1
    try:
        page = max(1, int(p.get("page") or 1))
    except Exception:
        page = 1
    if not tid:
        return {"list": [], "page": 1, "pagecount": 0, "limit": 0, "total": 0}
    if page <= 1:
        url = f"{HOST}/vtype/{tid}/"
    else:
        url = f"{HOST}/vtype/{tid}/page/{page}/"
    html_text = await _get(url)
    items = _parse_list(html_text) if html_text else []
    pagecount = page + 1 if len(items) >= 20 else page
    return {"list": items, "page": page, "pagecount": pagecount, "limit": 24, "total": page * 24}


async def detail(params, context):
    vid = str((params or {}).get("videoId") or (params or {}).get("id") or (params or {}).get("vod_id") or "").strip()
    if not vid:
        return {"list": []}
    url = f"{HOST}/v/video-{vid}/"
    html_text = await _get(url)
    title = vid
    pic = ""
    play_url = ""
    if html_text:
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.S)
        if m:
            title = clean_text(m.group(1))
        m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html_text)
        if m:
            pic = fix_url(m.group(1))
        play_url = extract_play(html_text)
    return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": "", "vod_play_sources": [{"name": "正片", "episodes": [{"name": "播放", "playId": play_url or url}]}]}]}


async def play(params, context):
    play_id = str((params or {}).get("playId") or (params or {}).get("id") or (params or {}).get("url") or "").strip()
    if not play_id:
        return {"parse": 0, "url": ""}
    if any(x in play_id for x in [".m3u8", ".mp4", ".flv"]):
        return {"parse": 0, "url": play_id, "header": {"User-Agent": UA, "Referer": HOST + "/"}}
    html_text = await _get(play_id)
    url = extract_play(html_text) if html_text else ""
    if url:
        return {"parse": 0, "url": url, "header": {"User-Agent": UA, "Referer": HOST + "/"}}
    return {"parse": 0, "url": play_id, "header": {"User-Agent": UA, "Referer": HOST + "/"}}


async def search(params, context):
    key = str((params or {}).get("wd") or (params or {}).get("key") or "").strip()
    page = 1
    try:
        page = max(1, int((params or {}).get("page") or 1))
    except Exception:
        page = 1
    if not key:
        return {"list": []}
    if page <= 1:
        url = f"{HOST}/?s={quote(key)}"
    else:
        url = f"{HOST}/page/{page}/?s={quote(key)}"
    html_text = await _get(url)
    items = _parse_list(html_text) if html_text else []
    return {"list": items}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
