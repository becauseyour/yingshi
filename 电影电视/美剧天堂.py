# -*- coding: utf-8 -*-
# @name 美剧天堂
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%94%B5%E5%BD%B1%E7%94%B5%E8%A7%86/%E7%BE%8E%E5%89%A7%E5%A4%A9%E5%A0%82.py
# @description 美剧天堂 meijutt.cc（OmniBox）

"""
美剧天堂 v1.0.0
站点: https://www.meijutt.cc
分类/详情/播放页解析；搜索站有验证码，暂不保证
"""

import html as html_mod
import re
from urllib.parse import quote, unquote, urljoin

from spider_runner import OmniBox, run

HOST = "https://www.meijutt.cc"
HOST_POOL = [
    "https://www.meijutt.cc",
]
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Referer": HOST + "/"}

CLASSES = [
    {"type_id": "1", "type_name": "魔幻科幻"},
    {"type_id": "2", "type_name": "灵异惊悚"},
    {"type_id": "3", "type_name": "都市情感"},
    {"type_id": "4", "type_name": "犯罪历史"},
    {"type_id": "5", "type_name": "选秀综艺"},
    {"type_id": "6", "type_name": "动漫卡通"},
]


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _clean(text):
    return re.sub(r"\s+", " ", text).strip() if text else ""


def _extract_text(html_str):
    text = re.sub(r"<[^>]+>", "", html_str or "").strip()
    return html_mod.unescape(text)


async def _get(path_or_url):
    global HOST
    url = path_or_url
    if url.startswith("/"):
        url = HOST + url
    last = None
    bases = [HOST] + [h for h in HOST_POOL if h != HOST]
    for base in bases:
        try:
            u = url
            if path_or_url.startswith("/"):
                u = base + path_or_url
            res = await OmniBox.request(
                u,
                {
                    "method": "GET",
                    "headers": {"User-Agent": UA, "Referer": base + "/"},
                    "timeout": 15,
                },
            )
            body = res.get("body") or ""
            if (res.get("statusCode") or 0) == 200 and body:
                HOST = base
                return body
            last = "status %s" % (res.get("statusCode"),)
        except Exception as e:
            last = e
            continue
    raise RuntimeError("请求失败: %s" % last)


async def home(params, context):
    try:
        return {"class": CLASSES, "list": [], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[home] %s" % e)
        return {"class": [], "list": [], "filters": {}}


def _parse_list_items(html, limit=40):
    videos = []
    seen = set()
    # 分类页结构
    items = re.findall(
        r'<div class="bor_img3_right">\s*<a href="(/meijutt/\d+\.html)"[^>]*title="([^"]*)"[^>]*>'
        r'<img[^>]*data-original="([^"]*)"[^>]*>.*?</a>\s*<em>([\d.]+)</em>',
        html,
        re.S,
    )
    for href, title, pic, score in items:
        if href in seen:
            continue
        seen.add(href)
        videos.append(
            {
                "vod_id": href,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "评分 %s" % score,
            }
        )
        if len(videos) >= limit:
            return videos
    # 首页/其它
    items2 = re.findall(
        r'<a href="(/meijutt/(\d+)\.html)"[^>]*title="([^"]*)"',
        html,
        re.S,
    )
    for href, vid, title in items2:
        if href in seen:
            continue
        seen.add(href)
        pic_m = re.search(
            r'<a href="%s"[^>]*>.*?<img[^>]*src="(https?://[^"]*)"' % re.escape(href),
            html,
            re.S,
        )
        pic = pic_m.group(1) if pic_m else ""
        videos.append(
            {
                "vod_id": href,
                "vod_name": title,
                "vod_pic": pic,
            }
        )
        if len(videos) >= limit:
            break
    return videos


async def category(params, context):
    try:
        p = params or {}
        tid = str(p.get("categoryId") or p.get("tid") or "1")
        page = _to_int(p.get("page"), 1) or 1
        if page == 1:
            path = "/mjtt/%s.html" % tid
        else:
            path = "/mjtt/%s-%s.html" % (tid, page)
        html = await _get(path)
        videos = _parse_list_items(html)
        page_match = re.search(r'href="[^"]*-(\d+)\.html"[^>]*>\s*末页', html)
        if not page_match:
            page_match = re.search(r"共(\d+)页", html)
        pagecount = int(page_match.group(1)) if page_match else max(page, 1)
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20,
        }
    except Exception as e:
        await OmniBox.log("error", "[category] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "limit": 20, "total": 0}


async def detail(params, context):
    try:
        p = params or {}
        vod_id = str(p.get("videoId") or p.get("id") or p.get("vod_id") or "").strip()
        if not vod_id:
            return {"list": []}
        if not vod_id.startswith("http"):
            path = vod_id if vod_id.startswith("/") else ("/" + vod_id)
            html = await _get(path)
            abs_url = HOST + path
        else:
            html = await _get(vod_id)
            abs_url = vod_id

        vod = {"vod_id": vod_id if not vod_id.startswith("http") else re.sub(r"^https?://[^/]+", "", vod_id)}
        m = re.search(
            r'<div class="info-title"><span>(【.*?】)</span><h1>([^<]+)</h1>\((\d{4})\)</div>',
            html,
        )
        if m:
            vod["vod_name"] = m.group(2).strip()
            vod["vod_year"] = m.group(3)
            vod["vod_area"] = re.sub(r"[\[\]【】]", "", m.group(1)).strip()
        else:
            m2 = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
            if m2:
                vod["vod_name"] = m2.group(1).strip()

        pic_match = re.search(
            r'<img[^>]*(?:data-src|data-original|src)="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"',
            html,
            re.I,
        )
        if pic_match:
            vod["vod_pic"] = pic_match.group(1)

        for li in re.findall(r"<li>(.*?)</li>", html, re.S):
            clean = _extract_text(li)
            if clean.startswith("主演："):
                actors = clean.replace("主演：", "").replace("更多>>", "").strip()
                if actors and actors not in ("内详", ""):
                    vod["vod_actor"] = actors
            elif clean.startswith("小分类："):
                vod["type_name"] = clean.replace("小分类：", "").strip()
            elif clean.startswith("地区："):
                area_text = clean.replace("地区：", "").strip()
                area_match = re.match(r"([^\s更新]+)", area_text)
                if area_match:
                    vod["vod_area"] = area_match.group(1)
            elif clean.startswith("状态："):
                vod["vod_remarks"] = clean.replace("状态：", "").strip()

        for part in re.findall(r"<p[^>]*>(.*?)</p>", html, re.S):
            clean = _extract_text(part)
            if len(clean) > 30 and "下载" not in clean and "magnet" not in clean:
                vod["vod_content"] = clean
                break

        sources = {}
        tab_labels = re.findall(r"<label[^>]*>\s*([^<]+)\s*<em>\[(\d+)\]</em>", html)
        tab_ids = re.findall(r'id="play_(\d+)"', html)
        tab_splits = re.split(r'<div class="tabs-list[^"]*"\s*id="play_\d+"', html)
        for i, play_id in enumerate(tab_ids):
            tab_name = tab_labels[i][0].strip() if i < len(tab_labels) else ("线路%s" % (i + 1))
            section = tab_splits[i + 1] if i + 1 < len(tab_splits) else ""
            end = re.search(r'<div class="tabs-list|<div class="o_list_cn', section)
            if end:
                section = section[: end.start()]
            episodes = re.findall(r'href="(/meijuplay/[^"]+)"[^>]*>([^<]+)', section)
            if episodes:
                ep_list = []
                for ep_url, ep_name in episodes:
                    ep_list.append({"name": _clean(ep_name) or "正片", "playId": HOST + ep_url})
                sources[tab_name] = ep_list

        # 网盘/磁力
        gvar_matches = re.findall(r'var\s+GvodUrls\d+\s*=\s*"([^"]*)"', html)
        for gvar in gvar_matches:
            for part in gvar.split("###"):
                if "$" not in part:
                    continue
                name, link_url = part.split("$", 1)
                name = _clean(name) or "下载"
                if "pan.quark.cn" in link_url:
                    src = "夸克网盘"
                elif "pan.xunlei.com" in link_url:
                    src = "迅雷网盘"
                elif "pan.baidu.com" in link_url:
                    src = "百度网盘"
                elif link_url.startswith("ed2k://"):
                    src = "ed2k"
                elif link_url.startswith("magnet:"):
                    src = "磁力"
                else:
                    src = "其他"
                sources.setdefault(src, []).append({"name": name, "playId": link_url})

        download_order = ["夸克网盘", "迅雷网盘", "百度网盘", "ed2k", "磁力", "其他"]
        streaming = [k for k in sources if k not in download_order and sources[k]]
        downloads = [k for k in download_order if k in sources and sources[k]]
        play_sources = []
        for src_name in streaming + downloads:
            play_sources.append({"name": src_name, "episodes": sources[src_name]})

        vod["vod_play_sources"] = play_sources
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", "[detail] %s" % e)
        return {"list": []}


async def search(params, context):
    """搜索站有验证码，尽量尝试，失败返回空列表。"""
    try:
        p = params or {}
        key = str(p.get("keyword") or p.get("wd") or "").strip()
        if not key:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        # GET 尝试
        path = "/search.php?searchword=" + quote(key)
        try:
            html = await _get(path)
        except Exception:
            html = ""
        if "系统安全验证" in html or "vdcode" in html:
            await OmniBox.log("warn", "[search] 触发验证码，跳过")
            return {"list": [], "page": 1, "pagecount": 0, "total": 0}
        videos = _parse_list_items(html)
        return {
            "list": videos,
            "page": 1,
            "pagecount": 1 if videos else 0,
            "total": len(videos),
        }
    except Exception as e:
        await OmniBox.log("error", "[search] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}


async def play(params, context):
    try:
        p = params or {}
        play_id = str(p.get("playId") or p.get("url") or "").strip()
        headers = {
            "User-Agent": UA,
            "Referer": HOST + "/",
        }
        if not play_id:
            return {"urls": [], "parse": 0, "header": headers}

        # 网盘/磁力直接返回
        if any(
            x in play_id
            for x in (
                "pan.quark.cn",
                "pan.xunlei.com",
                "pan.baidu.com",
                "magnet:",
                "ed2k://",
            )
        ):
            return {
                "urls": [{"name": "打开", "url": play_id}],
                "parse": 0,
                "header": headers,
            }

        # 播放页取 m3u8
        if "/meijuplay/" in play_id:
            path = play_id
            if play_id.startswith("http"):
                path = re.sub(r"^https?://[^/]+", "", play_id)
            html = await _get(path)
            m = re.search(
                r'var\s+now\s*=\s*(?:unescape\()?["\']([^"\']+)',
                html,
            )
            if m:
                url = m.group(1)
                if "%" in url:
                    url = unquote(url)
                if ".m3u8" in url or url.startswith("http"):
                    return {
                        "urls": [{"name": "播放", "url": url}],
                        "parse": 0,
                        "header": headers,
                    }
            m2 = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
            if m2:
                return {
                    "urls": [{"name": "播放", "url": m2.group(1)}],
                    "parse": 0,
                    "header": headers,
                }

        if re.search(r"\.(m3u8|mp4)(\?|$)", play_id, re.I):
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
        await OmniBox.log("error", "[play] %s" % e)
        return {"urls": [], "parse": 0, "header": {}}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
