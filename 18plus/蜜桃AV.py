# -*- coding: utf-8 -*-
# @name 蜜桃AV
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/%E8%9C%9C%E6%A1%83AV.py
# @description 蜜桃AV（OmniBox）

"""
蜜桃AV v1.0.0
主站: https://20260807bb-bnm.mitaoava02.top
"""

import json
import re
from urllib.parse import quote, unquote, urljoin

from spider_runner import OmniBox, run

HOSTS = [
    "https://20260807bb-bnm.mitaoava02.top",
]
HOST = HOSTS[0]
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

CLASSES = [
    {"type_id": "guochanwuma", "type_name": "国产无码"},
    {"type_id": "ribenkoujiao", "type_name": "日本口爆"},
    {"type_id": "ribenwuma", "type_name": "日本无码"},
    {"type_id": "ribenqunhuan", "type_name": "日本群交"},
    {"type_id": "guochanremen", "type_name": "国产热门"},
    {"type_id": "haibiantoupai", "type_name": "海边偷拍"},
    {"type_id": "touqingchezhen", "type_name": "偷情车震"},
    {"type_id": "wuwudongman", "type_name": "污污动漫"},
    {"type_id": "lalaqunjiao", "type_name": "拉拉群交"},
    {"type_id": "gayqunjiao", "type_name": "Gay群交"},
    {"type_id": "oumeijingxuan", "type_name": "欧美精选"},
    {"type_id": "ziweishouyin", "type_name": "自慰手淫"},
    {"type_id": "madouchuanmei", "type_name": "麻豆传媒"},
    {"type_id": "tianmeichuanmei", "type_name": "天美传媒"},
    {"type_id": "huangjiahuaren", "type_name": "皇家华人"},
    {"type_id": "jingdongyingye", "type_name": "精东影业"},
    {"type_id": "qidianchuanmei", "type_name": "起点传媒"},
]


def _to_int(v, d=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return d


def _clean(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip()


def _abs(url):
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    return urljoin(HOST + "/", url)


def _is_media(url):
    return bool(re.search(r"\.(m3u8|mp4|flv)(\?|$)", str(url or ""), re.I))


async def _get(path_or_url):
    global HOST
    last = None
    for base in [HOST] + [h for h in HOSTS if h != HOST]:
        url = path_or_url if path_or_url.startswith("http") else base + path_or_url
        try:
            res = await OmniBox.request(
                url,
                {
                    "method": "GET",
                    "headers": {"User-Agent": UA, "Referer": base + "/"},
                    "timeout": 15,
                },
            )
            body = res.get("body") or ""
            if (res.get("statusCode") or 0) == 200 and body and "Just a moment" not in body:
                HOST = base
                return body
            last = res.get("statusCode")
        except Exception as e:
            last = e
    raise RuntimeError("请求失败 %s" % last)


def _parse_list(html):
    videos = []
    seen = set()
    cards = re.findall(r'<li[^>]*class="[^"]*content-item[^"]*"[^>]*>(.*?)</li>', html, re.S | re.I)
    if not cards:
        cards = re.findall(r'href="(/index\.php/vod/detail/id/\d+\.html)"[^>]*>(.*?)</a>', html, re.S | re.I)
        for href, block in cards:
            vid_m = re.search(r"/id/(\d+)", href)
            if not vid_m or vid_m.group(1) in seen:
                continue
            seen.add(vid_m.group(1))
            title = ""
            tm = re.search(r'title="([^"]+)"', block)
            if tm:
                title = _clean(tm.group(1))
            pic = ""
            pm = re.search(r'(?:data-src|data-original|src)="([^"]+)"', block)
            if pm:
                pic = _abs(pm.group(1))
            videos.append({"vod_id": href, "vod_name": title or vid_m.group(1), "vod_pic": pic, "vod_remarks": ""})
        return videos
    for card in cards:
        href_m = re.search(r'href="(/index\.php/vod/detail/id/(\d+)\.html)"', card)
        if not href_m:
            href_m = re.search(r'href="([^"]*detail/id/(\d+)[^"]*)"', card)
        if not href_m:
            continue
        href, vid = href_m.group(1), href_m.group(2)
        if vid in seen:
            continue
        seen.add(vid)
        title = ""
        for pat in [r'title="([^"]+)"', r"<h\d[^>]*>.*?<a[^>]*>(.*?)</a>"]:
            m = re.search(pat, card, re.S | re.I)
            if m:
                title = _clean(m.group(1))
                if title:
                    break
        pic = ""
        for pat in [r'data-src="([^"]+)"', r'data-original="([^"]+)"', r'src="([^"]+)"']:
            m = re.search(pat, card, re.I)
            if m:
                pic = _abs(m.group(1))
                break
        remark = ""
        rm = re.search(r'class="[^"]*note[^"]*"[^>]*>(.*?)</', card, re.S | re.I)
        if rm:
            remark = _clean(rm.group(1))
        videos.append({"vod_id": href, "vod_name": title or vid, "vod_pic": pic, "vod_remarks": remark})
    return videos


def _extract_urls(html):
    urls = []
    seen = set()

    def add(label, u):
        u = unquote(str(u or "").strip())
        if not u or u in seen:
            return
        seen.add(u)
        urls.append((label, u))

    for m in re.finditer(r"var\s+player_[a-zA-Z0-9_]+\s*=\s*(\{.*?\});", html, re.S):
        try:
            data = json.loads(m.group(1))
            u = data.get("url") or ""
            if u:
                add("主线路", unquote(u))
        except Exception:
            pass
    m = re.search(r'var\s+now\s*=\s*["\']([^"\']+)["\']', html)
    if m:
        add("直连", m.group(1))
    for m in re.finditer(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4)(?:\?[^\s"\'<>]*)?)', html):
        add("提取", m.group(1))
    return urls


async def home(params, context):
    return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("tid") or "guochanwuma")
        page = _to_int(p.get("page"), 1) or 1
        if page > 1:
            path = "/index.php/vod/type/id/%s/page/%s.html" % (tid, page)
        else:
            path = "/index.php/vod/type/id/%s.html" % tid
        html = await _get(path)
        videos = _parse_list(html)
        pages = [int(x) for x in re.findall(r"/page/(\d+)\.html", html)]
        pc = max(pages) if pages else max(page, 1)
        return {"list": videos, "page": page, "pagecount": pc, "limit": 24, "total": pc * 24}
    except Exception as e:
        await OmniBox.log("error", "[category] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "limit": 24, "total": 0}


async def detail(params, context):
    try:
        p = params or {}
        vid = str(p.get("videoId") or p.get("id") or "").strip()
        if not vid:
            return {"list": []}
        path = vid if vid.startswith("/") or vid.startswith("http") else "/index.php/vod/detail/id/%s.html" % vid
        if not path.startswith("http") and not path.startswith("/"):
            path = "/" + path
        html = await _get(path)
        title_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        title = _clean(title_m.group(1) if title_m else "") or vid
        pic = ""
        pm = re.search(r'property="og:image"[^>]+content="([^"]+)"', html)
        if pm:
            pic = _abs(pm.group(1))
        # play links
        play_links = re.findall(
            r'href="([^"]*(?:/vod/play/|/index\.php/vod/play/)[^"]*)"[^>]*>(.*?)</a>',
            html,
            re.S | re.I,
        )
        sources = []
        if play_links:
            eps = []
            for href, name in play_links:
                full = _abs(href)
                eps.append({"name": _clean(name) or "播放", "playId": full})
            sources.append({"name": "在线", "episodes": eps})
        else:
            # try extract direct
            extracted = _extract_urls(html)
            if extracted:
                sources.append(
                    {
                        "name": "直连",
                        "episodes": [{"name": lab, "playId": u} for lab, u in extracted],
                    }
                )
            else:
                id_m = re.search(r"/id/(\d+)", vid)
                pid = id_m.group(1) if id_m else vid
                play_page = "%s/index.php/vod/play/id/%s/sid/1/nid/1.html" % (HOST, pid)
                sources.append({"name": "默认", "episodes": [{"name": "正片", "playId": play_page}]})
        return {
            "list": [
                {
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_play_sources": sources,
                }
            ]
        }
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
        path = "/index.php/vod/search.html?wd=%s&page=%s" % (quote(key), page)
        html = await _get(path)
        videos = _parse_list(html)
        return {"list": videos, "page": page, "pagecount": page + (1 if videos else 0), "total": len(videos)}
    except Exception as e:
        await OmniBox.log("error", "[search] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}


async def play(params, context):
    try:
        p = params or {}
        play_id = str(p.get("playId") or p.get("url") or "").strip()
        headers = {"User-Agent": UA, "Referer": HOST + "/"}
        if not play_id:
            return {"urls": [], "parse": 0, "header": headers}
        if _is_media(play_id):
            return {"urls": [{"name": "播放", "url": play_id}], "parse": 0, "header": headers}
        # play page
        html = await _get(play_id if play_id.startswith("http") else play_id)
        for lab, u in _extract_urls(html):
            if _is_media(u) or u.startswith("http"):
                return {"urls": [{"name": lab, "url": u}], "parse": 0 if _is_media(u) else 1, "header": headers}
        return {"urls": [{"name": "播放", "url": play_id}], "parse": 1, "header": headers}
    except Exception as e:
        await OmniBox.log("error", "[play] %s" % e)
        return {"urls": [], "parse": 0, "header": {}}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
