# -*- coding: utf-8 -*-
# @name Hanime1
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/Hanime1.py
# @description Hanime1 里番源（OmniBox）：多镜像自愈、分类筛选、原画直链、相关推荐

"""
Hanime1 — OmniBox 适配版
镜像: hanime1.me / hanime1.com 等
列表: /search?genre=&page=
详情: /watch?v= 提取 <source> mp4
说明: Cloudflare 可能拦截机房 IP，家庭网络一般可正常使用
"""

import re
import html as html_lib
from urllib.parse import quote, urlparse

from spider_runner import OmniBox, run

MIRROR_POOL = [
    "https://hanime1.me",
    "https://www.hanime1.me",
    "https://hanime1.com",
    "https://www.hanime101.com",
    "https://www.hanime999.cc",
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

_site_url = MIRROR_POOL[0]
_site_ready = False

CLASSES = [
    {"type_name": "里番", "type_id": "裏番"},
    {"type_name": "泡面番", "type_id": "泡麵番"},
    {"type_name": "Motion Anime", "type_id": "Motion Anime"},
    {"type_name": "3DCG", "type_id": "3DCG"},
    {"type_name": "2.5D", "type_id": "2.5D"},
    {"type_name": "AI生成", "type_id": "AI生成"},
    {"type_name": "MMD", "type_id": "MMD"},
    {"type_name": "Cosplay", "type_id": "Cosplay"},
    {"type_name": "新番预告", "type_id": "新番預告"},
    {"type_name": "2D动画", "type_id": "2D動畫"},
]

SORT_FILTER = {
    "key": "sort",
    "name": "排序方式",
    "value": [
        {"n": "最新上传", "v": ""},
        {"n": "本日排行", "v": "本日排行"},
        {"n": "本週排行", "v": "本週排行"},
        {"n": "本月排行", "v": "本月排行"},
    ],
}


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _headers(referer=""):
    return {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": referer or (_site_url + "/"),
        "Connection": "keep-alive",
    }


async def _raw_get(url, timeout=12):
    res = await OmniBox.request(
        url,
        {"method": "GET", "headers": _headers(), "timeout": timeout},
    )
    code = res.get("statusCode") or res.get("status") or 0
    text = res.get("body") or ""
    return code, text


async def _check_host(base):
    try:
        code, text = await _raw_get(base.rstrip("/") + "/", timeout=8)
        # CF 挑战页通常很短且含 cloudflare / challenge
        if code == 200 and len(text) > 3000 and "cf-browser-verification" not in text.lower():
            return True
        # 有些节点 200 但内容完整
        if code == 200 and ("hanime" in text.lower() or "/watch?v=" in text):
            return True
        return False
    except Exception:
        return False


async def _refresh_site():
    global _site_url, _site_ready
    for host in MIRROR_POOL:
        if await _check_host(host):
            _site_url = host.rstrip("/")
            _site_ready = True
            try:
                await OmniBox.setCache("hanime1_site", _site_url)
            except Exception:
                pass
            await OmniBox.log("info", "[host] 选用 %s" % _site_url)
            return True
    # 全挂也保留默认，避免空
    _site_url = MIRROR_POOL[0]
    _site_ready = False
    await OmniBox.log("warn", "[host] 镜像均异常，暂用 %s" % _site_url)
    return False


async def _ensure_site(force_node=""):
    global _site_url, _site_ready
    if force_node and force_node.startswith("http"):
        _site_url = force_node.rstrip("/")
        _site_ready = True
        try:
            await OmniBox.setCache("hanime1_site", _site_url)
        except Exception:
            pass
        return
    if _site_ready:
        return
    try:
        cached = await OmniBox.getCache("hanime1_site")
        if isinstance(cached, str) and cached.startswith("http"):
            _site_url = cached.rstrip("/")
            if await _check_host(_site_url):
                _site_ready = True
                return
    except Exception:
        pass
    await _refresh_site()


async def _fetch(path_or_url, retry=True):
    await _ensure_site()
    if path_or_url.startswith("//"):
        url = "https:" + path_or_url
    elif path_or_url.startswith("http"):
        url = path_or_url
    else:
        url = _site_url + (path_or_url if path_or_url.startswith("/") else "/" + path_or_url)

    code, text = await _raw_get(url)
    if code == 200 and text and "cf-browser-verification" not in text.lower():
        return text

    if retry:
        old = urlparse(_site_url).netloc
        await _refresh_site()
        new = urlparse(_site_url).netloc
        if new and old != new:
            url2 = url.replace(old, new)
            code2, text2 = await _raw_get(url2)
            if code2 == 200 and text2:
                return text2
    return text or ""


def _parse_list(html):
    videos = []
    seen = set()
    for block in html.split("/watch?v=")[1:]:
        m = re.match(r'^([^"&\s#]+)', block)
        if not m:
            continue
        vod_id = m.group(1).strip()
        if not vod_id or vod_id in seen:
            continue
        seen.add(vod_id)
        chunk = block[:1500]

        pic = ""
        pm = re.search(r'<img[^>]+(?:src|data-src)=["\']([^"\']+)["\']', chunk, re.I)
        if pm:
            pic = pm.group(1).strip()
            if pic.startswith("//"):
                pic = "https:" + pic

        title = "未知标题"
        tm = re.search(r"home-rows-videos-title[^>]*>\s*([^<]+)", chunk)
        if tm:
            title = tm.group(1).strip()
        else:
            tm = re.search(r'class="title"[^>]*>\s*([^<]+)', chunk)
            if tm:
                title = tm.group(1).strip()
            else:
                tm = re.search(r'(?:title|alt)=["\']([^"\']{2,})["\']', chunk, re.I)
                if tm:
                    title = tm.group(1).strip()
        title = html_lib.unescape(title)
        if title.lower() in ("", "thumb", "img"):
            title = "视频 %s" % vod_id

        remarks = []
        dm = re.search(r'class="duration"[^>]*>\s*([^<]+)', chunk)
        if dm:
            remarks.append(dm.group(1).strip())
        vm = re.search(r'class="stat-item">\s*([^<]+)', chunk)
        if vm:
            remarks.append(vm.group(1).strip())

        videos.append(
            {
                "vod_id": "%s@@@%s@@@%s" % (vod_id, title, pic),
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": " | ".join(remarks),
            }
        )
    return videos


def _node_filter():
    choices = [{"n": "自动优选", "v": ""}]
    for u in MIRROR_POOL:
        domain = urlparse(u).netloc
        choices.append({"n": domain, "v": u})
    return {"key": "node", "name": "切换线路", "value": choices}


def _extract_sources(html):
    links = []
    for src in re.findall(r'<source[^>]+src=["\']([^"\']+)["\']', html, re.I):
        links.append(src.strip())
    if not links:
        links = re.findall(r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', html, re.I)
    parsed = []
    seen = set()
    for link in links:
        if not link or link in seen:
            continue
        seen.add(link)
        if link.startswith("//"):
            link = "https:" + link
        rm = re.search(r"(\d+)p", link, re.I)
        if rm:
            quality = rm.group(0).upper()
            weight = int(rm.group(1))
        else:
            quality = "默认"
            weight = 0
        parsed.append((weight, quality, link))
    parsed.sort(key=lambda x: x[0], reverse=True)
    return parsed


async def home(params, context):
    try:
        await OmniBox.log("info", "[home] from=%s" % (context or {}).get("from", "web"))
        await _ensure_site()
        filters = {c["type_id"]: [SORT_FILTER, _node_filter()] for c in CLASSES}
        # 首页取里番第一页作推荐
        html = await _fetch("/search?genre=%s&page=1" % quote("裏番"))
        videos = _parse_list(html)[:36]
        return {"class": CLASSES, "list": videos, "filters": filters}
    except Exception as e:
        await OmniBox.log("error", "[home] 失败: %s" % e)
        return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    try:
        tid = str((params or {}).get("categoryId") or "裏番")
        page = _to_int((params or {}).get("page"), 1) or 1
        extend = (params or {}).get("filters") or {}
        node = ""
        sort_val = ""
        if isinstance(extend, dict):
            node = str(extend.get("node") or "")
            sort_val = str(extend.get("sort") or "")
        await _ensure_site(force_node=node)
        await OmniBox.log("info", "[category] %s page=%s node=%s" % (tid, page, _site_url))

        qs = "genre=%s&page=%s" % (quote(tid), page)
        if sort_val:
            qs += "&sort=%s" % quote(sort_val)
        html = await _fetch("/search?%s" % qs)
        videos = _parse_list(html)
        pagecount = page + 1 if len(videos) >= 24 else page
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 40,
            "total": pagecount * 40,
        }
    except Exception as e:
        await OmniBox.log("error", "[category] 失败: %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 40}


async def detail(params, context):
    try:
        raw = str((params or {}).get("videoId") or "").strip()
        if not raw:
            return {"list": []}
        await OmniBox.log("info", "[detail] %s" % raw[:80])
        await _ensure_site()

        passed_title = passed_pic = ""
        if "@@@" in raw:
            parts = raw.split("@@@")
            vod_id = parts[0]
            if len(parts) > 1:
                passed_title = parts[1]
            if len(parts) > 2:
                passed_pic = parts[2]
        else:
            vod_id = raw

        html = await _fetch("/watch?v=%s" % quote(vod_id))
        title = passed_title
        if not title:
            tm = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
            if tm:
                title = re.split(r"&nbsp;-|\s*-\s*", tm.group(1))[0].strip()
            else:
                title = vod_id
        title = html_lib.unescape(title)

        pic = passed_pic
        if not pic:
            pm = re.search(
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                html,
                re.I,
            )
            if pm:
                pic = pm.group(1)

        desc = ""
        dm = re.search(
            r'<meta[^>]+(?:property=["\']og:description["\']|name=["\']description["\'])[^>]+content=["\']([^"\']+)["\']',
            html,
            re.I,
        )
        if dm:
            desc = html_lib.unescape(dm.group(1).strip())
        content = "节点: %s\n%s" % (_site_url, desc or "Hanime1")

        sources = _extract_sources(html)
        episodes = []
        for weight, quality, link in sources:
            episodes.append({"name": quality, "playId": link})
        if not episodes:
            episodes.append({"name": "原页", "playId": "/watch?v=%s" % vod_id})

        play_sources = [{"name": "原画直连", "episodes": episodes}]

        # 相关推荐
        related = []
        seen = {str(vod_id)}
        for block in html.split("/watch?v=")[1:]:
            m = re.match(r'^([^"&\s#]+)', block)
            if not m:
                continue
            rid = m.group(1)
            if rid in seen:
                continue
            seen.add(rid)
            chunk = block[:1200]
            name = ""
            tm = re.search(r"home-rows-videos-title[^>]*>\s*([^<]+)", chunk)
            if tm:
                name = tm.group(1).strip()
            else:
                tm = re.search(r'class="title"[^>]*>\s*([^<]+)', chunk)
                if tm:
                    name = tm.group(1).strip()
            name = html_lib.unescape(name) or ("推荐 %02d" % len(related))
            related.append({"name": name[:40], "playId": "/watch?v=%s" % rid})
            if len(related) >= 24:
                break
        if related:
            play_sources.append({"name": "相关推荐", "episodes": related})

        vod = {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "高清",
            "vod_content": content,
            "vod_play_sources": play_sources,
        }
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", "[detail] 失败: %s" % e)
        return {"list": []}


async def search(params, context):
    try:
        key = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 40}
        await OmniBox.log("info", "[search] %s page=%s" % (key, page))
        await _ensure_site()
        html = await _fetch("/search?query=%s&page=%s" % (quote(key), page))
        videos = _parse_list(html)
        return {
            "list": videos,
            "page": page,
            "pagecount": page + 1 if len(videos) >= 24 else page,
            "limit": 40,
            "total": len(videos),
        }
    except Exception as e:
        await OmniBox.log("error", "[search] 失败: %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 40}


async def play(params, context):
    try:
        play_id = str((params or {}).get("playId") or "").strip()
        flag = str((params or {}).get("flag") or "play")
        if not play_id:
            raise ValueError("playId 为空")
        await OmniBox.log("info", "[play] %s" % play_id[:120])
        await _ensure_site()

        url = play_id
        # 相关推荐：二次解析 watch 页
        if play_id.startswith("/watch?v=") or "watch?v=" in play_id:
            path = play_id if play_id.startswith("/") else "/" + play_id.split("/", 3)[-1]
            if "watch?v=" in play_id and not play_id.startswith("/"):
                m = re.search(r"/watch\?v=[^&\s]+", "/" + play_id)
                path = m.group(0) if m else play_id
            html = await _fetch(path)
            sources = _extract_sources(html)
            if sources:
                url = sources[0][2]
            else:
                url = _site_url + (path if path.startswith("/") else "/" + path)

        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = _site_url + url

        headers = {
            "User-Agent": UA,
            "Referer": _site_url + "/",
            "Origin": _site_url,
        }
        is_media = any(x in url.lower() for x in (".mp4", ".m3u8", ".webm"))
        return {
            "urls": [{"name": "播放", "url": url}] if url else [],
            "flag": flag,
            "header": headers,
            "parse": 0 if is_media else 1,
        }
    except Exception as e:
        await OmniBox.log("error", "[play] 失败: %s" % e)
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
