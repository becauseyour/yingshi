# -*- coding: utf-8 -*-
# @name 每日大赛
# @version 1.1.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/18plus/每日大赛.py
# @description 每日大赛站源（OmniBox 适配版 v1.1）：修复可用域名、分类/列表/详情解析；已去掉 localProxy

"""
每日大赛 — OmniBox 适配版 v1.1.0

修复点：
1. 主机探测改为「200 + 页面含 article」判定，避免选中空壳域名
2. 主站优先: www.mrds66.com / mrds.com
3. 列表/详情改用正则解析（不强制依赖 pyquery）
4. dplayer data-config 支持单引号 JSON
"""

import json
import re
from urllib.parse import quote, urljoin

from spider_runner import OmniBox, run

PAGE_SIZE = 90
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 经实测可返回完整内容的域名靠前
DYNAMIC_HOSTS = [
    "https://www.mrds66.com",
    "https://mrds.com",
    "https://www.mrds.com",
    "https://mrds66.com",
]
FALLBACK_HOST = "https://www.mrds66.com"

_host = ""
_headers = {}


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _is_video_format(url):
    low = (url or "").lower()
    return any(ext in low for ext in [".m3u8", ".mp4", ".ts", ".flv", ".mkv"])


def _abs_url(url, host=None):
    host = host or _host or FALLBACK_HOST
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    if url.startswith("/"):
        return host.rstrip("/") + url
    return host.rstrip("/") + "/" + url


async def _http_get(url, timeout=15):
    res = await OmniBox.request(
        url,
        {
            "method": "GET",
            "headers": _headers or {
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            "timeout": timeout,
        },
    )
    status = res.get("statusCode") or 0
    body = res.get("body") or ""
    final_url = res.get("url") or url
    return status, body, final_url


async def _ensure_host():
    global _host, _headers
    if _host:
        return _host

    base_headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }

    for url in DYNAMIC_HOSTS:
        try:
            res = await OmniBox.request(
                url + "/",
                {"method": "GET", "headers": base_headers, "timeout": 8},
            )
            status = res.get("statusCode") or 0
            body = res.get("body") or ""
            final = (res.get("url") or url).rstrip("/")
            # 必须有 article 内容，避免选中空壳/跳转页
            if status == 200 and len(body) > 5000 and ("<article" in body or "/archives/" in body):
                _host = final
                _headers = dict(base_headers)
                _headers.update({"Origin": _host, "Referer": f"{_host}/"})
                await OmniBox.log("info", f"[init] 站点: {_host} (size={len(body)})")
                return _host
            await OmniBox.log("warn", f"[init] 跳过 {url}: status={status}, size={len(body)}")
        except Exception as e:
            await OmniBox.log("warn", f"[init] 探测失败 {url}: {e}")
            continue

    _host = FALLBACK_HOST
    _headers = dict(base_headers)
    _headers.update({"Origin": _host, "Referer": f"{_host}/"})
    await OmniBox.log("info", f"[init] 回退站点: {_host}")
    return _host


def _parse_categories(html):
    classes = []
    seen = set()
    # 导航分类: /category/xxx/
    for href, name in re.findall(
        r'href="(/category/[^"]+/)"[^>]*>([^<]+)</a>',
        html or "",
    ):
        name = name.strip()
        if not name or href in seen:
            continue
        seen.add(href)
        classes.append({"type_name": name, "type_id": href})
    if not classes:
        classes = [{"type_name": "每日大赛", "type_id": "/category/mrds/"}]
    return classes


def _parse_list(html, tid=""):
    videos = []
    seen = set()
    is_folder = "/mrdg" in (tid or "")
    articles = re.findall(r"<article[\s\S]*?</article>", html or "", re.I)
    for art in articles:
        href_m = re.search(r'href="(/archives/\d+/[^"]*|/[^"]*\.html)"', art)
        if not href_m:
            href_m = re.search(r'href="([^"]*archives[^"]*)"', art)
        if not href_m:
            continue
        href = href_m.group(1)
        if href in seen:
            continue
        seen.add(href)

        title = ""
        for pat in [
            r"<h2[^>]*>([\s\S]*?)</h2>",
            r'class="[^"]*(?:entry-title|post-title)[^"]*"[^>]*>([\s\S]*?)</',
            r'title="([^"]+)"',
        ]:
            tm = re.search(pat, art, re.I)
            if tm:
                title = re.sub(r"<[^>]+>", "", tm.group(1)).strip()
                if title:
                    break
        if not title:
            continue

        pic = ""
        bm = re.search(r"loadBannerDirect\('([^']+)'", art)
        if bm:
            pic = bm.group(1)
        else:
            im = re.search(r'(https?://[^"\'\s)]+\.(?:jpg|jpeg|png|webp))', art, re.I)
            if im:
                pic = im.group(1)

        remarks = ""
        rm = re.search(r"(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|\d{4}-\d{1,2}-\d{1,2})", art)
        if rm:
            remarks = rm.group(1)
        else:
            tm = re.search(r"<time[^>]*>([\s\S]*?)</time>", art, re.I)
            if tm:
                remarks = re.sub(r"<[^>]+>", "", tm.group(1)).strip()

        item = {
            "vod_id": f"{href}{'@folder' if is_folder else ''}",
            "vod_name": title,
            "vod_pic": _abs_url(pic) if pic and not pic.startswith("http") else pic,
            "vod_remarks": remarks,
        }
        if is_folder:
            item["vod_tag"] = "folder"
        videos.append(item)
    return videos


def _extract_dplayer_urls(html):
    """解析 dplayer data-config（单/双引号 JSON）"""
    episodes = []
    used = set()
    configs = []
    # JSON 本身不含未转义引号，直接 [^'"] 最稳
    configs.extend(re.findall(r"data-config\s*=\s*'([^']*)'", html or ""))
    configs.extend(re.findall(r'data-config\s*=\s*"([^"]*)"', html or ""))

    if not configs:
        for m in re.finditer(
            r'https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*',
            (html or "").replace("\\/", "/"),
        ):
            configs.append(json.dumps({"video": {"url": m.group(0)}}))
            break

    for i, raw in enumerate(configs, start=1):
        try:
            cfg = json.loads(raw)
            video_url = ""
            if isinstance(cfg, dict):
                video_url = ((cfg.get("video") or {}).get("url") or "").replace("\\/", "/")
            if not video_url:
                continue
            name = f"视频{i}"
            # data-video_title 优先
            mtitle = re.search(
                r'data-video_title="([^"]*)"[^>]*data-config\s*=\s*[\'"]' + re.escape(raw[:30]),
                html or "",
            )
            if not mtitle:
                mtitle = re.search(r'data-video_title="([^"]+)"', html or "")
            if mtitle and mtitle.group(1).strip():
                name = mtitle.group(1).strip()
            base = name
            n = 2
            while name in used:
                name = f"{base} {n}"
                n += 1
            used.add(name)
            episodes.append({"name": name, "playId": video_url})
        except Exception:
            continue
    return episodes


async def home(params, context):
    try:
        await OmniBox.log("info", f"[home] from={(context or {}).get('from', 'web')}")
        host = await _ensure_host()
        status, body, _ = await _http_get(host + "/", timeout=15)
        if status != 200 or not body:
            return {"class": [{"type_name": "每日大赛", "type_id": "/category/mrds/"}], "list": []}
        classes = _parse_categories(body)
        videos = _parse_list(body)
        return {"class": classes, "list": videos, "filters": {}}
    except Exception as e:
        await OmniBox.log("error", f"[home] 失败: {e}")
        return {"class": [], "list": [], "filters": {}}


async def category(params, context):
    try:
        host = await _ensure_host()
        tid = str((params or {}).get("categoryId") or "/category/mrds/")
        page = _to_int((params or {}).get("page"), 1) or 1
        await OmniBox.log("info", f"[category] categoryId={tid}, page={page}")

        if tid.startswith("http"):
            base_url = tid.rstrip("/")
        else:
            path = tid if tid.startswith("/") else f"/{tid}"
            base_url = f"{host}{path}".rstrip("/")

        if page <= 1:
            url = base_url + "/"
        else:
            # /category/xxx/2/ 或 /page/2/
            if "/category/" in base_url or "/tag/" in base_url:
                url = f"{base_url}/{page}/"
            else:
                url = f"{host}/page/{page}/"

        status, body, _ = await _http_get(url, timeout=15)
        if status != 200:
            return {"list": [], "page": page, "pagecount": 9999, "limit": PAGE_SIZE, "total": 0}

        videos = _parse_list(body, tid)
        return {
            "list": videos,
            "page": page,
            "pagecount": 9999 if len(videos) >= 10 else page,
            "limit": PAGE_SIZE,
            "total": 999999,
        }
    except Exception as e:
        await OmniBox.log("error", f"[category] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": PAGE_SIZE}


async def detail(params, context):
    try:
        host = await _ensure_host()
        req_id = str((params or {}).get("videoId") or "")
        if not req_id:
            return {"list": []}
        await OmniBox.log("info", f"[detail] videoId={req_id}")
        url = req_id if req_id.startswith("http") else _abs_url(req_id, host)

        status, body, _ = await _http_get(url, timeout=15)
        if status != 200 or not body:
            return {"list": []}

        title = ""
        for pat in [
            r'class="[^"]*post-title[^"]*"[^>]*>([\s\S]*?)</',
            r"<h1[^>]*>([\s\S]*?)</h1>",
            r"<title>([^<]+)</title>",
        ]:
            m = re.search(pat, body, re.I)
            if m:
                title = re.sub(r"<[^>]+>", "", m.group(1)).split("-")[0].strip()
                if title:
                    break
        title = title or "每日大赛"

        episodes = _extract_dplayer_urls(body)

        # 兜底：正文里的观看链接
        if not episodes:
            for href, text in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', body):
                t = re.sub(r"<[^>]+>", "", text).strip()
                if any(k in t for k in ("点击观看", "观看", "播放", "第一弹")) and href:
                    episodes.append({"name": t or "视频", "playId": _abs_url(href, host)})

        # 再兜底：直接找 m3u8
        if not episodes:
            for m in re.finditer(r'https?://[^"\'\s<>\\]+\.m3u8[^"\'\s<>\\]*', body):
                episodes.append({"name": "正片", "playId": m.group(0).replace("\\/", "/")})
                break

        content = ""
        tags = re.findall(r'class="[^"]*(?:post-tags|tags|keywords)[^"]*"[^>]*>[\s\S]*?</(?:div|section)', body, re.I)
        if tags:
            names = re.findall(r"<a[^>]*>([^<]+)</a>", tags[0])
            content = " ".join(n.strip() for n in names if n.strip())

        vod = {
            "vod_id": req_id,
            "vod_name": title,
            "vod_pic": "",
            "vod_content": content or title,
        }
        if episodes:
            vod["vod_play_sources"] = [{"name": "每日大赛", "episodes": episodes}]
        else:
            await OmniBox.log("warn", "[detail] 未解析到播放地址")
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] 失败: {e}")
        return {"list": []}


async def search(params, context):
    try:
        host = await _ensure_host()
        key = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": PAGE_SIZE}
        await OmniBox.log("info", f"[search] keyword={key}, page={page}")
        if page <= 1:
            url = f"{host}/search/{quote(key)}/"
        else:
            url = f"{host}/search/{quote(key)}/{page}/"
        status, body, _ = await _http_get(url, timeout=15)
        if status != 200:
            return {"list": [], "page": page, "pagecount": 9999, "limit": PAGE_SIZE, "total": 0}
        videos = _parse_list(body)
        return {
            "list": videos,
            "page": page,
            "pagecount": 9999 if len(videos) >= 10 else page,
            "limit": PAGE_SIZE,
            "total": 999999,
        }
    except Exception as e:
        await OmniBox.log("error", f"[search] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": PAGE_SIZE}


async def play(params, context):
    try:
        play_id = str((params or {}).get("playId") or "").strip()
        flag = str((params or {}).get("flag") or "play")
        if not play_id:
            raise ValueError("playId 为空")
        parse = 0 if _is_video_format(play_id) else 1
        await OmniBox.log("info", f"[play] playId={play_id[:120]}, parse={parse}")
        headers = dict(_headers) if _headers else {"User-Agent": UA}
        # 播放域名防盗链
        headers["Referer"] = (_host or FALLBACK_HOST) + "/"
        headers["Origin"] = _host or FALLBACK_HOST
        return {
            "urls": [{"name": "播放", "url": play_id}],
            "flag": flag,
            "header": headers,
            "parse": parse,
        }
    except Exception as e:
        await OmniBox.log("error", f"[play] 失败: {e}")
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run(
        {
            "home": home,
            "category": category,
            "detail": detail,
            "search": search,
            "play": play,
        }
    )
