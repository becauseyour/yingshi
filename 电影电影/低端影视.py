# -*- coding: utf-8 -*-
# @name 低端影视
# @version 1.0.0
# @description 低端影视 m.ddys.net（OmniBox）：分类筛选/搜索/多线路播放
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%94%B5%E5%BD%B1%E7%94%B5%E8%A7%86/低端影视.py
import html
import json
import re
from urllib.parse import quote, unquote

from spider_runner import OmniBox, run

HOST = "https://m.ddys.net"
UA = (
    "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"
)

CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "连续剧"},
    {"type_id": "26", "type_name": "短剧"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "20", "type_name": "纪录片"},
]
MOVIE_TYPES = [
    ("动作片", "6"), ("喜剧片", "7"), ("爱情片", "8"), ("科幻片", "9"),
    ("恐怖片", "10"), ("剧情片", "11"), ("战争片", "12"), ("动画片", "21"), ("纪录片", "20"),
]
SERIES_TYPES = [
    ("国产剧", "13"), ("港台剧", "14"), ("日韩剧", "15"), ("欧美剧", "16"), ("海外剧", "22"),
]
MOVIE_GENRES = "喜剧,爱情,恐怖,动作,科幻,剧情,战争,警匪,犯罪,动画,奇幻,武侠,冒险,枪战,悬疑,惊悚"
SERIES_GENRES = "爱情,古装,战争,偶像,喜剧,家庭,犯罪,动作,奇幻,剧情,历史,经典,乡村,情景"
SHORT_GENRES = "重生,穿越,现代,反转,都市,古装,闪婚,悬疑,男频,逆袭"
VARIETY_GENRES = "选秀,情感,访谈,播报,旅游,音乐,美食,纪实,曲艺,生活,游戏,财经,求职"
ANIME_GENRES = "情感,科幻,热血,推理,搞笑,冒险,萝莉,校园,动作,机战,运动,战争,益智,励志,其他"
MOVIE_AREAS = "中国大陆,中国香港,中国台湾,美国,日本,韩国,英国,法国,德国,意大利,西班牙,印度,泰国,俄罗斯,加拿大"
OTHER_AREAS = "中国大陆,美国,香港,台湾,日本,韩国,英国,法国,德国"
YEARS = "2026,2025,2024,2023,2022,2021,2020,2019,2018,2017,2016,2015,2014,2013,2012,2011,2010,更早"

CARD_RE = re.compile(
    r'<a\b([^>]*class=["\'][^"\']*stui-vodlist__thumb[^"\']*["\'][^>]*)>(.*?)</a>',
    re.I | re.S,
)
PLAYLIST_RE = re.compile(
    r'<h3>(.*?)</h3>\s*</div>\s*<ul\b[^>]*class=["\'][^"\']*stui-content__playlist[^"\']*["\'][^>]*>(.*?)</ul>',
    re.I | re.S,
)
ANCHOR_RE = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.I | re.S)


def _attr(tag, name):
    m = re.search(r"(?:^|\s)" + re.escape(name) + r'\s*=\s*["\']([^"\']*)', tag or "", re.I | re.S)
    return html.unescape(m.group(1)) if m else ""


def _clean(value):
    value = re.sub(r"<script\b[^>]*>.*?</script>", "", value or "", flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _match(source, pattern):
    m = re.search(pattern, source or "", re.I | re.S)
    return m.group(1) if m else ""


def _page(value):
    try:
        return max(1, int(value))
    except (ValueError, TypeError):
        return 1


def _values(names):
    return [{"name": "全部", "value": ""}] + [{"name": n, "value": n} for n in names.split(",")]


def _group(name, key, values):
    return {"key": key, "name": name, "value": values}


def _filters():
    filters = {}
    for item in CLASSES:
        tid = item["type_id"]
        groups = []
        if tid in ("1", "2"):
            types = MOVIE_TYPES if tid == "1" else SERIES_TYPES
            groups.append(
                _group(
                    "类型",
                    "type",
                    [{"name": "全部", "value": tid}] + [{"name": n, "value": v} for n, v in types],
                )
            )
        genre = {
            "2": SERIES_GENRES,
            "26": SHORT_GENRES,
            "3": VARIETY_GENRES,
            "4": ANIME_GENRES,
        }.get(tid, MOVIE_GENRES)
        groups.append(_group("剧情", "genre", _values(genre)))
        if tid != "26":
            areas = OTHER_AREAS if tid in ("3", "4") else MOVIE_AREAS
            groups.append(_group("地区", "area", _values(areas)))
            groups.append(_group("年份", "year", _values(YEARS)))
        filters[tid] = groups
    return filters


def _category_path(tid, page, extend):
    ext = extend if isinstance(extend, dict) else {}
    selected = {k: str(ext.get(k) or "").strip() for k in ("type", "area", "genre", "year")}
    if not any(selected.values()):
        return "/class/{}-{}.html".format(tid, page)
    allowed = MOVIE_TYPES if tid == "1" else SERIES_TYPES if tid == "2" else []
    type_id = selected["type"]
    if type_id not in [tid] + [v for _, v in allowed]:
        type_id = tid
    fields = [""] * 12
    fields[0], fields[1], fields[3], fields[11] = (
        type_id,
        selected["area"],
        selected["genre"],
        selected["year"],
    )
    if page > 1:
        fields[8] = str(page)
    return "/show/" + "-".join(quote(f, safe="") for f in fields) + ".html"


def _cards(source, limit=80):
    cards = {}
    for attrs, body in CARD_RE.findall(source or ""):
        path = _attr(attrs, "href")
        m = re.search(r"/html/(\d+)\.html", path)
        if not m or m.group(1) in cards:
            continue
        name = _clean(_attr(attrs, "title"))
        if not name:
            continue
        pic = _attr(attrs, "data-original") or _attr(attrs, "data-src")
        if pic.startswith("//"):
            pic = "https:" + pic
        elif pic.startswith("/"):
            pic = HOST + pic
        cards[m.group(1)] = {
            "vod_id": m.group(1),
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": _clean(
                _match(body, r'<span\b[^>]*class=["\'][^"\']*pic-text[^"\']*["\'][^>]*>(.*?)</span>')
            ),
        }
        if len(cards) >= limit:
            break
    return list(cards.values())


def _page_count(source, current):
    total = _match(
        source,
        r'<li\b[^>]*class=["\'][^"\']*\bnum\b[^"\']*["\'][^>]*>\s*<a[^>]*>\s*\d+/(\d+)',
    )
    try:
        return max(current, int(total))
    except (ValueError, TypeError):
        return current


async def _get(path):
    if not path.startswith("/"):
        path = "/" + path
    url = HOST + path
    res = await OmniBox.request(
        url,
        {
            "method": "GET",
            "headers": {
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,*/*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": HOST + "/",
            },
            "timeout": 15,
        },
    )
    status = int(res.get("statusCode") or 0)
    if status and (status < 200 or status >= 400):
        raise IOError("HTTP %s @ %s" % (status, url))
    return str(res.get("body") or "")


def _normalize_filters(params):
    raw = params.get("filters") or params.get("filter") or params.get("extend") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = {}
    return raw if isinstance(raw, dict) else {}


async def home(params, context):
    try:
        cards = _cards(await _get("/index.html"), 72)
        await OmniBox.log("info", "[低端影视][home] list=%s" % len(cards))
        return {"class": CLASSES, "filters": _filters(), "list": cards}
    except Exception as e:
        await OmniBox.log("error", "[低端影视][home] %s" % e)
        return {"class": CLASSES, "filters": _filters(), "list": []}


async def category(params, context):
    tid = str(params.get("categoryId") or params.get("type_id") or params.get("tid") or "1")
    page = _page(params.get("page") or params.get("pg") or 1)
    extend = _normalize_filters(params)
    if tid not in {c["type_id"] for c in CLASSES}:
        return {"list": [], "page": page, "pagecount": page, "total": 0}
    try:
        source = await _get(_category_path(tid, page, extend))
        cards = _cards(source, 40)
        pages = _page_count(source, page)
        if len(cards) >= 20:
            pages = max(pages, page + 1)
        await OmniBox.log(
            "info", "[低端影视][category] tid=%s page=%s list=%s" % (tid, page, len(cards))
        )
        return {"list": cards, "page": page, "pagecount": pages, "total": pages * max(1, len(cards))}
    except Exception as e:
        await OmniBox.log("error", "[低端影视][category] %s" % e)
        return {"list": [], "page": page, "pagecount": page, "total": 0}


async def search(params, context):
    keyword = str(params.get("keyword") or params.get("wd") or params.get("key") or "").strip()
    page = _page(params.get("page") or params.get("pg") or 1)
    if not keyword:
        return {"list": [], "page": page, "pagecount": 0, "total": 0}
    fields = [keyword] + [""] * 13
    if page > 1:
        fields[10] = str(page)
    path = "/so/" + "-".join(quote(v, safe="") for v in fields) + ".html"
    try:
        source = await _get(path)
        cards = _cards(source, 40)
        pages = _page_count(source, page)
        if len(cards) >= 20:
            pages = max(pages, page + 1)
        await OmniBox.log(
            "info", "[低端影视][search] kw=%s list=%s" % (keyword, len(cards))
        )
        return {"list": cards, "page": page, "pagecount": pages, "total": pages * max(1, len(cards))}
    except Exception as e:
        await OmniBox.log("error", "[低端影视][search] %s" % e)
        return {"list": [], "page": page, "pagecount": 0, "total": 0}


async def detail(params, context):
    vod_id = str(params.get("videoId") or params.get("id") or params.get("vod_id") or "").strip()
    m = re.search(r"/html/(\d+)", vod_id)
    if m:
        vod_id = m.group(1)
    if not vod_id.isdigit():
        return {"list": []}
    try:
        source = await _get("/html/{}.html".format(vod_id))
        title = _clean(_match(source, r"<h1\b[^>]*>(.*?)</h1>"))
        poster_block = _match(
            source,
            r'<div\b[^>]*class=["\'][^"\']*stui-content__thumb[^"\']*["\'][^>]*>(.*?)</div>',
        )
        poster = _attr(_match(poster_block, r"<img\b([^>]*)>"), "data-original")
        if not poster:
            poster = _attr(_match(source, r"<img\b([^>]*)>"), "data-original")
        if poster.startswith("//"):
            poster = "https:" + poster
        elif poster.startswith("/"):
            poster = HOST + poster
        description = _clean(
            _match(source, r'<span\b[^>]*class=["\']detail-content["\'][^>]*>(.*?)</span>')
        )
        play_sources = []
        for name, block in PLAYLIST_RE.findall(source):
            episodes = []
            for attrs, body in ANCHOR_RE.findall(block):
                route = re.search(
                    r"/play/" + re.escape(vod_id) + r"/(\d+)/(\d+)\.html",
                    _attr(attrs, "href"),
                )
                if not route:
                    continue
                label = _clean(body).replace("$", " ").replace("#", " ") or "播放"
                play_id = "{}:{}:{}".format(vod_id, route.group(1), route.group(2))
                episodes.append({"name": label, "playId": play_id})
            if episodes:
                play_sources.append({"name": _clean(name) or "线路", "episodes": episodes})
        await OmniBox.log(
            "info",
            "[低端影视][detail] id=%s sources=%s" % (vod_id, len(play_sources)),
        )
        return {
            "list": [
                {
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": poster,
                    "vod_content": description,
                    "vod_play_sources": play_sources,
                }
            ]
        }
    except Exception as e:
        await OmniBox.log("error", "[低端影视][detail] %s" % e)
        return {"list": []}


async def play(params, context):
    raw = str(params.get("playId") or params.get("id") or "").strip()
    parts = raw.split(":")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return {"urls": [], "parse": 0, "header": {}}
    try:
        source = await _get("/play/{}/{}/{}.html".format(*parts))
        raw_json = _match(source, r"var\s+player_aaaa\s*=\s*(\{.*?\})\s*;?\s*</script>")
        if not raw_json:
            return {"urls": [], "parse": 0, "header": {}}
        player = json.loads(raw_json)
        url = player.get("url") or ""
        encryption = int(player.get("encrypt") or 0)
        if encryption == 1:
            url = unquote(url)
        elif encryption == 2:
            url = base64.b64decode(url).decode("utf-8")
        if not re.match(r"^https?://\S+$", url, re.I):
            return {"urls": [], "parse": 0, "header": {}}
        direct = bool(re.search(r"\.(?:m3u8|mp4)(?:[?#]|$)", url, re.I))
        await OmniBox.log("info", "[低端影视][play] direct=%s url=%s" % (direct, url[:80]))
        return {
            "urls": [{"name": "默认线路", "url": url}],
            "parse": 0 if direct else 1,
            "header": {
                "User-Agent": UA,
                "Referer": HOST + "/",
            },
        }
    except Exception as e:
        await OmniBox.log("error", "[低端影视][play] %s" % e)
        return {"urls": [], "parse": 0, "header": {}}


run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
