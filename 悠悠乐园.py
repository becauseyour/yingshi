# -*- coding: utf-8 -*-
# @name 悠悠乐园
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/Silent1566/OmniBox-Spider/main/影视/采集/悠悠乐园.py
# @indexs 1
# @description 悠悠乐园站源（OmniBox 适配版）：多域名、player_aaaa 解析、列表正则

import re
import json
import base64
import html as html_lib
from urllib.parse import quote, unquote

from spider_runner import OmniBox, run

SITE_BASE = "https://nzgyz-58190-thndpm.miyoooooo666oom72.top"
SITE_URL = SITE_BASE + "/yoooooo"
PLAY_SITE = SITE_BASE
PLAY_URL2 = "https://yb1.yoooooo666oo7.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

CLASS_LIST = [
    {"type_id": "20", "type_name": "国产"},
    {"type_id": "114", "type_name": "传媒系列"},
    {"type_id": "142", "type_name": "探花系列"},
    {"type_id": "21", "type_name": "日本有码"},
    {"type_id": "26", "type_name": "国产精品"},
    {"type_id": "29", "type_name": "国产自拍"},
    {"type_id": "91", "type_name": "网曝系列"},
    {"type_id": "115", "type_name": "麻豆传媒"},
    {"type_id": "119", "type_name": "天美传媒"},
    {"type_id": "167", "type_name": "综合探花"},
    {"type_id": "143", "type_name": "91沈先生"},
    {"type_id": "157", "type_name": "网红黑料"},
]

YEAR_FILTER = [
    {"n": "全部", "v": ""},
    {"n": "2026", "v": "2026"},
    {"n": "2025", "v": "2025"},
    {"n": "2024", "v": "2024"},
    {"n": "2023", "v": "2023"},
    {"n": "2022", "v": "2022"},
    {"n": "2021", "v": "2021"},
    {"n": "2020", "v": "2020"},
]
FILTERS = {c["type_id"]: [{"key": "year", "name": "年份", "value": YEAR_FILTER}] for c in CLASS_LIST}


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _unesc(s):
    try:
        return html_lib.unescape(s or "").strip()
    except Exception:
        return (s or "").strip()


def _fix_url(u):
    if not u:
        return ""
    if u.startswith("http"):
        return u
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return SITE_BASE + u
    return u


def _encode_id(raw_id):
    safe = base64.urlsafe_b64encode(str(raw_id).encode("utf-8")).decode("utf-8").rstrip("=")
    return "v_" + safe


def _decode_id(safe_id):
    if not str(safe_id).startswith("v_"):
        return str(safe_id)
    b64 = str(safe_id)[2:]
    pad = len(b64) % 4
    if pad:
        b64 += "=" * (4 - pad)
    try:
        return base64.urlsafe_b64decode(b64.encode("utf-8")).decode("utf-8")
    except Exception:
        return str(safe_id)


async def _fetch(url, referer=""):
    if url.startswith("/"):
        if not url.startswith("/yoooooo"):
            url = SITE_URL + url
        else:
            url = SITE_BASE + url
    res = await OmniBox.request(
        url,
        {
            "method": "GET",
            "headers": {
                "User-Agent": UA,
                "Referer": referer or (SITE_URL + "/"),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            "timeout": 15,
        },
    )
    if (res.get("statusCode") or 0) not in (200, 301, 302):
        return ""
    return res.get("body") or ""


def _extract_player_url(html_text):
    if not html_text or len(html_text) < 50:
        return ""
    for var_name in ("player_aaaa", "player_data"):
        start_idx = html_text.find(var_name)
        if start_idx == -1:
            continue
        brace_start = html_text.find("{", start_idx)
        if brace_start == -1:
            continue
        depth, in_str, esc, end_idx = 0, False, False, -1
        for ci in range(brace_start, len(html_text)):
            c = html_text[ci]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        end_idx = ci + 1
                        break
        if end_idx > brace_start:
            try:
                player_data = json.loads(html_text[brace_start:end_idx])
                video_url = player_data.get("url", "")
                encrypt = str(player_data.get("encrypt", "0"))
                if encrypt == "1":
                    video_url = unquote(video_url)
                elif encrypt == "2":
                    try:
                        video_url = unquote(base64.b64decode(video_url).decode("utf-8", errors="ignore"))
                    except Exception:
                        pass
                video_url = video_url.replace(r"\/", "/")
                if video_url and video_url.startswith("http"):
                    return video_url
            except Exception:
                pass
    m = re.search(r'https?://[^"\'\s<>\\]+\.m3u8[^"\'\s<>\\]*', html_text)
    if m:
        return m.group(0).replace(r"\/", "/")
    m = re.search(r'https?://[^"\'\s<>\\]+\.mp4[^"\'\s<>\\]*', html_text)
    if m:
        return m.group(0).replace(r"\/", "/")
    return ""


async def _fetch_play_m3u8(play_path):
    if not play_path.startswith("/"):
        play_path = "/" + play_path
    for domain in (PLAY_URL2, PLAY_SITE):
        html = await _fetch(domain + play_path, referer=domain + "/")
        m3u8 = _extract_player_url(html)
        if m3u8:
            return m3u8
    return ""


def _parse_list_html(html_text):
    videos, seen = [], set()
    items = re.findall(
        r'<div[^>]+class=["\'][^"\']*movie-list-item[^"\']*["\'][^>]*>([\s\S]*?)(?=<div[^>]+class=["\'][^"\']*movie-list-item|$)',
        html_text or "",
        re.I,
    )
    if not items:
        items = re.findall(r'(<a[^>]+href=["\'][^"\']*/voddetail/\d+/[^"\']*["\'][\s\S]*?</a>)', html_text or "", re.I)
    for item in items:
        href_match = re.search(r'href=["\']([^"\']*/voddetail/(\d+)/[^"\']*)["\']', item, re.I)
        if not href_match:
            continue
        vod_id = href_match.group(2)
        if vod_id in seen:
            continue
        seen.add(vod_id)
        title = ""
        tm = re.search(r'class=["\'][^"\']*movie-title[^"\']*["\'][^>]*title=["\']([^"\']+)["\']', item, re.I)
        if tm:
            title = tm.group(1)
        if not title:
            tt = re.search(r'class=["\'][^"\']*movie-title[^"\']*["\'][^>]*>([\s\S]*?)</', item, re.I)
            if tt:
                title = re.sub(r"<[^>]+>", "", tt.group(1)).strip()
        if not title:
            ta = re.search(r'title=["\']([^"\']+)["\']', item, re.I)
            if ta:
                title = ta.group(1)
        title = re.sub(r"影片信息$", "", title or "").strip()
        pic = ""
        om = re.search(r'data-original=["\']([^"\']+)["\']', item, re.I)
        if om:
            pic = om.group(1)
        else:
            sm = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', item, re.I)
            if sm and not sm.group(1).startswith("data:"):
                pic = sm.group(1)
        rating_m = re.search(r'class=["\'][^"\']*movie-rating[^"\']*["\'][^>]*>([\s\S]*?)<', item, re.I)
        remarks = (("%s分" % rating_m.group(1).strip()) if rating_m else "")
        if title:
            videos.append({
                "vod_id": _encode_id(vod_id),
                "vod_name": _unesc(title),
                "vod_pic": _fix_url(pic),
                "vod_remarks": remarks,
            })
    return videos


async def home(params, context):
    try:
        await OmniBox.log("info", f"[home] from={(context or {}).get('from', 'web')}")
        return {"class": CLASS_LIST, "list": [], "filters": FILTERS}
    except Exception as e:
        await OmniBox.log("error", f"[home] 失败: {e}")
        return {"class": CLASS_LIST, "list": [], "filters": {}}


async def category(params, context):
    try:
        tid = str((params or {}).get("categoryId") or "20").strip("/")
        page = _to_int((params or {}).get("page"), 1) or 1
        filters = (params or {}).get("filters") or {}
        year = str(filters.get("year") or "")
        await OmniBox.log("info", f"[category] categoryId={tid}, page={page}, year={year}")
        if year:
            req_url = "%s/s/year/%s/page/%d/" % (SITE_URL, year, page)
        else:
            req_url = "%s/t/%s/page/%d/" % (SITE_URL, tid, page)
        html = await _fetch(req_url, referer=SITE_URL + "/")
        if not html or len(html) < 500:
            if year:
                req_url = "%s/s/year/%s/page/%d/" % (PLAY_URL2, year, page)
            else:
                req_url = "%s/t/%s/page/%d/" % (PLAY_URL2, tid, page)
            html = await _fetch(req_url, referer=PLAY_URL2 + "/")
        vod_list = _parse_list_html(html)
        return {
            "list": vod_list,
            "page": page,
            "pagecount": 999 if len(vod_list) >= 15 else page,
            "limit": 30,
            "total": 9999,
        }
    except Exception as e:
        await OmniBox.log("error", f"[category] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 30}


async def detail(params, context):
    try:
        raw_id = str((params or {}).get("videoId") or "")
        if not raw_id:
            return {"list": []}
        real_id = _decode_id(raw_id)
        await OmniBox.log("info", f"[detail] videoId={raw_id}")
        detail_url = "%s/voddetail/%s/" % (PLAY_URL2, real_id)
        html = await _fetch(detail_url, referer=PLAY_URL2 + "/")
        if not html or len(html) < 500:
            detail_url = "%s/voddetail/%s/" % (PLAY_SITE, real_id)
            html = await _fetch(detail_url, referer=PLAY_SITE + "/")
        vod_name = ""
        m_h1 = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", html or "", re.I)
        if m_h1:
            vod_name = re.sub(r"<[^>]+>", "", m_h1.group(1)).strip()
        vod_pic = ""
        om = re.search(r'data-original=["\']([^"\']+)["\']', html or "", re.I)
        if om:
            vod_pic = om.group(1)
        vod_year = ""
        my = re.search(r"/s/year/(\d+)/", html or "")
        if my:
            vod_year = my.group(1)
        vod_remarks = ""
        ms = re.search(r"状态：([^<]+)", html or "")
        if ms:
            vod_remarks = ms.group(1).strip()
        play_links = []
        seen_sid = set()
        for href, sid, text in re.findall(
            r'<a[^>]+href=["\']([^"\']*/v/\d+/sid/(\d+)/nid/\d+/[^"\']*)["\'][^>]*>([\s\S]*?)</a>',
            html or "",
            re.I,
        ):
            if sid in seen_sid:
                continue
            seen_sid.add(sid)
            c_text = re.sub(r"<[^>]+>", "", text).strip() or "播放"
            play_links.append({"text": c_text, "href": href})
        if not play_links:
            for href in re.findall(
                r'<a[^>]+class=["\'][^"\']*btn[^"\']*["\'][^>]*href=["\']([^"\']*/v/[^"\']*)["\']',
                html or "",
                re.I,
            ):
                play_links.append({"text": "播放", "href": href})
        sources = []
        for item in play_links:
            m3u8 = await _fetch_play_m3u8(item["href"])
            play_id = m3u8 if m3u8 else item["href"]
            sources.append({"name": item["text"], "episodes": [{"name": item["text"], "playId": play_id}]})
        vod = {
            "vod_id": raw_id,
            "vod_name": _unesc(vod_name) or real_id,
            "vod_pic": _fix_url(vod_pic),
            "vod_year": vod_year,
            "vod_remarks": _unesc(vod_remarks),
            "vod_content": "",
        }
        if sources:
            vod["vod_play_sources"] = sources
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", f"[detail] 失败: {e}")
        return {"list": []}


async def search(params, context):
    try:
        wd = str((params or {}).get("keyword") or (params or {}).get("wd") or "").strip()
        page = _to_int((params or {}).get("page"), 1) or 1
        if not wd:
            return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 0}
        await OmniBox.log("info", f"[search] keyword={wd}, page={page}")
        search_url = "%s/s/%s/page/%d/" % (SITE_URL, quote(wd), page)
        html = await _fetch(search_url, referer=SITE_URL + "/")
        if not html or len(html) < 500:
            search_url = "%s/s/%s/page/%d/" % (PLAY_URL2, quote(wd), page)
            html = await _fetch(search_url, referer=PLAY_URL2 + "/")
        vod_list = _parse_list_html(html)
        return {
            "list": vod_list,
            "page": page,
            "pagecount": page if len(vod_list) < 15 else page + 1,
            "limit": len(vod_list),
            "total": 9999,
        }
    except Exception as e:
        await OmniBox.log("error", f"[search] 失败: {e}")
        return {"list": [], "page": 1, "pagecount": 0, "total": 0, "limit": 0}


async def play(params, context):
    try:
        play_id = str((params or {}).get("playId") or "").strip()
        flag = str((params or {}).get("flag") or "play")
        if not play_id:
            raise ValueError("playId 为空")
        await OmniBox.log("info", f"[play] playId={play_id[:80]}")
        if play_id.startswith("http") and any(x in play_id for x in (".m3u8", ".mp4")):
            return {
                "urls": [{"name": "播放", "url": play_id}],
                "flag": flag,
                "header": {"User-Agent": UA, "Referer": PLAY_SITE + "/"},
                "parse": 0,
            }
        if play_id.startswith("http"):
            return {
                "urls": [{"name": "播放", "url": play_id}],
                "flag": flag,
                "header": {"User-Agent": UA, "Referer": SITE_URL + "/"},
                "parse": 0,
            }
        m3u8 = await _fetch_play_m3u8(play_id)
        if m3u8:
            return {
                "urls": [{"name": "播放", "url": m3u8}],
                "flag": flag,
                "header": {"User-Agent": UA, "Referer": PLAY_SITE + "/"},
                "parse": 0,
            }
        path = play_id if play_id.startswith("/") else ("/" + play_id)
        return {
            "urls": [{"name": "播放", "url": PLAY_URL2 + path}],
            "flag": flag,
            "header": {"User-Agent": UA, "Referer": PLAY_URL2 + "/"},
            "parse": 0,
        }
    except Exception as e:
        await OmniBox.log("error", f"[play] 失败: {e}")
        return {"urls": [], "flag": (params or {}).get("flag", "play"), "header": {}, "parse": 0}


if __name__ == "__main__":
    run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
