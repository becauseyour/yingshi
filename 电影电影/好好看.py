# -*- coding: utf-8 -*-
# @name 好好看
# @version 1.1.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%94%B5%E5%BD%B1%E7%94%B5%E8%A7%86/好好看.py
# @description 好好看影视（hhkan 多镜像）：电影/连续剧/Netflix/综艺/动漫/短剧，首页聚合热门

"""
好好看 — OmniBox v1.1.0

官网镜像: www.hhkan0.com ~ www.hhkan4.com
分类对齐站内导航: 电影 / 连续剧 / Netflix / 综艺 / 动漫 / 短剧
首页: 解析首页卡片；若为空则聚合各分类第一页热门
播放: player_aaaa → m3u8/mp4；失败 parse=1
"""

import json
import re
import time
from urllib.parse import quote, urljoin

from spider_runner import OmniBox, run

HOSTS = [
    "https://www.hhkan0.com",
    "https://www.hhkan1.com",
    "https://www.hhkan2.com",
    "https://www.hhkan3.com",
    "https://www.hhkan4.com",
]
HOST = HOSTS[0]
UA = (
    "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
)

# 站内常见 type id（MacCMS 风格；连续剧多为 2，Netflix 多为独立 id）
CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "连续剧"},
    {"type_id": "netflix", "type_name": "Netflix"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "5", "type_name": "短剧"},
]

# Netflix / 连续剧 备用路径关键字
_CATE_SLUG = {
    "1": ["1", "dianying", "movie"],
    "2": ["2", "lianxuju", "tv", "dianshiju"],
    "netflix": ["netflix", "6", "20", "21"],
    "3": ["3", "zongyi"],
    "4": ["4", "dongman", "anime"],
    "5": ["5", "duanju", "short"],
}


def _page(v):
    try:
        return max(1, int(v))
    except (ValueError, TypeError):
        return 1


def _abs(u, base=None):
    base = base or HOST
    u = str(u or "").strip()
    if not u or u == "<nil>":
        return ""
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http"):
        return u
    return urljoin(base.rstrip("/") + "/", u.lstrip("/"))


async def _req(url, referer=None):
    res = await OmniBox.request(
        url,
        {
            "method": "GET",
            "headers": {
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": referer or (HOST + "/"),
            },
            "timeout": 15,
        },
    )
    body = res.get("body")
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="ignore")
    text = str(body or "")
    status = int(res.get("statusCode") or 0)
    final = str(res.get("url") or res.get("finalUrl") or url)
    return status, text, final


async def _ensure_host():
    global HOST
    cache_key = "hhkan_host_v11"
    try:
        cached = await OmniBox.getCache(cache_key)
        if isinstance(cached, dict) and cached.get("host"):
            HOST = cached["host"]
            return HOST
    except Exception:
        pass

    for h in HOSTS:
        try:
            st, text, final = await _req(h + "/", referer=h + "/")
            if st and st >= 400:
                continue
            if "cdndefend" in text or "verifying your browser" in text.lower():
                # 部分环境 JS 挑战后仍可解析，若正文很长继续用
                if len(text) < 2000:
                    continue
            if len(text) < 800:
                continue
            m = re.search(r"https?://(?:www\.)?hhkan\d*\.com", final)
            HOST = m.group(0) if m else h
            try:
                await OmniBox.setCache(
                    cache_key, {"expiresAt": int(time.time()) + 300, "host": HOST}
                )
            except Exception:
                pass
            await OmniBox.log("info", "[好好看] host=%s" % HOST)
            return HOST
        except Exception as e:
            await OmniBox.log("warn", "[好好看] host fail %s %s" % (h, e))
            continue
    HOST = HOSTS[0]
    return HOST


def _parse_cards(html):
    cards = []
    seen = set()

    def add(vid, title, pic="", remarks=""):
        vid = str(vid or "").strip()
        title = re.sub(r"\s+", " ", str(title or "")).strip()
        if not vid or not title or vid in seen:
            return
        if title in ("查看更多", "更多", "首页", "电影", "连续剧"):
            return
        seen.add(vid)
        cards.append(
            {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": _abs(pic),
                "vod_remarks": remarks.strip(),
            }
        )

    # A. detail / play 链接 + 邻近标题/图
    for m in re.finditer(
        r'href="((?:https?://[^"]+)?/(?:index\.php/)?vod/(?:detail|play)/id/(\d+)[^"]*)"',
        html,
        re.I,
    ):
        vid = m.group(2)
        window = html[max(0, m.start() - 200) : m.end() + 500]
        title = ""
        for pat in (
            r'title="([^"]{2,80})"',
            r'alt="([^"]{2,80})"',
            r"<h[1-6][^>]*>\s*([^<]{2,80})",
            r'class="[^"]*title[^"]*"[^>]*>\s*([^<]{2,80})',
        ):
            tm = re.search(pat, window, re.I)
            if tm:
                title = tm.group(1).strip()
                break
        pic = ""
        pm = re.search(
            r'(?:data-original|data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)',
            window,
            re.I,
        )
        if pm:
            pic = pm.group(1)
        remarks = ""
        for rp in (
            r"豆瓣[:：]?\s*([\d.]+)",
            r'class="[^"]*(?:pic-text|text-right|remarks|v_note|module-item-note)[^"]*"[^>]*>([^<]+)',
            r"(更新至[^<]{1,20}|全\d+集|正片|HD|抢先)",
        ):
            rm = re.search(rp, window, re.I)
            if rm:
                remarks = rm.group(1).strip()
                break
        add(vid, title, pic, remarks)

    # B. module-item / public-list-box 卡片
    for block in re.finditer(
        r'class="[^"]*(?:module-item|public-list-box|vodlist_item|myui-vodlist__box)[^"]*"[\s\S]{0,900}',
        html,
        re.I,
    ):
        chunk = block.group(0)
        im = re.search(r"/id/(\d+)", chunk)
        if not im:
            continue
        vid = im.group(1)
        title = ""
        tm = re.search(r'(?:title|alt)="([^"]{2,80})"', chunk)
        if tm:
            title = tm.group(1)
        pic = ""
        pm = re.search(
            r'(?:data-original|data-src|src)=["\']([^"\']+)', chunk, re.I
        )
        if pm:
            pic = pm.group(1)
        remarks = ""
        rm = re.search(
            r'class="[^"]*(?:pic-text|module-item-note|text-right)[^"]*"[^>]*>([^<]+)',
            chunk,
            re.I,
        )
        if rm:
            remarks = rm.group(1)
        add(vid, title, pic, remarks)

    # C. JSON 嵌入
    for jm in re.finditer(
        r'\{\s*"vod_id"\s*:\s*(\d+)\s*,\s*"vod_name"\s*:\s*"([^"]+)"[^\}]{0,400}\}',
        html,
    ):
        pic = ""
        pm = re.search(r'"vod_pic"\s*:\s*"([^"]+)"', jm.group(0))
        if pm:
            pic = pm.group(1).replace("\\/", "/")
        remarks = ""
        rm = re.search(r'"vod_remarks"\s*:\s*"([^"]*)"', jm.group(0))
        if rm:
            remarks = rm.group(1)
        add(jm.group(1), jm.group(2), pic, remarks)

    return cards


def _list_urls(tid, page):
    keys = _CATE_SLUG.get(str(tid), [str(tid)])
    urls = []
    for k in keys:
        urls.extend(
            [
                "%s/index.php/vod/show/id/%s/page/%s.html" % (HOST, k, page),
                "%s/vod/show/id/%s/page/%s.html" % (HOST, k, page),
                "%s/index.php/vodtype/%s-%s.html" % (HOST, k, page),
                "%s/vodtype/%s-%s.html" % (HOST, k, page),
                "%s/index.php/vod/type/id/%s/page/%s.html" % (HOST, k, page),
                "%s/index.php/vod/show/class/%s/page/%s.html" % (HOST, quote(str(k)), page),
            ]
        )
    # Netflix 文本分类
    if str(tid) == "netflix":
        urls[0:0] = [
            "%s/index.php/vod/show/class/Netflix/page/%s.html" % (HOST, page),
            "%s/vod/show/class/Netflix/page/%s.html" % (HOST, page),
            "%s/index.php/label/netflix.html" % HOST,
        ]
    return urls


def _search_urls(keyword, page):
    q = quote(keyword)
    return [
        "%s/index.php/vod/search/page/%s/wd/%s.html" % (HOST, page, q),
        "%s/vod/search/page/%s/wd/%s.html" % (HOST, page, q),
        "%s/index.php/vod/search/wd/%s/page/%s.html" % (HOST, q, page),
        "%s/index.php/ajax/suggest?mid=1&wd=%s&limit=30" % (HOST, q),
    ]


def _detail_urls(vid):
    return [
        "%s/index.php/vod/detail/id/%s.html" % (HOST, vid),
        "%s/vod/detail/id/%s.html" % (HOST, vid),
    ]


async def _get_html(urls):
    last = ""
    for url in urls:
        try:
            st, text, _ = await _req(url)
            if st and st >= 400 and st != 850:
                continue
            if "cdndefend" in text and len(text) < 2000:
                last = text
                continue
            if len(text) > 500:
                return text
            last = text
        except Exception:
            continue
    return last


async def home(params, context):
    try:
        await _ensure_host()
        html = await _get_html([HOST + "/", HOST + "/index.php", HOST + "/index.html"])
        cards = _parse_cards(html)
        # 首页若无卡片（SPA/懒加载），聚合电影+连续剧第一页
        if len(cards) < 8:
            for tid in ("1", "2", "netflix"):
                more = _parse_cards(await _get_html(_list_urls(tid, 1)))
                for c in more:
                    if c["vod_id"] not in {x["vod_id"] for x in cards}:
                        cards.append(c)
                if len(cards) >= 36:
                    break
        await OmniBox.log("info", "[好好看][home] host=%s n=%s" % (HOST, len(cards)))
        return {"class": CLASSES, "list": cards[:48], "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[好好看][home] %s" % e)
        return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    tid = str(
        (params or {}).get("categoryId")
        or (params or {}).get("type_id")
        or (params or {}).get("tid")
        or "1"
    )
    page = _page((params or {}).get("page") or (params or {}).get("pg") or 1)
    try:
        await _ensure_host()
        html = await _get_html(_list_urls(tid, page))
        cards = _parse_cards(html)
        pagecount = page + (1 if len(cards) >= 12 else 0)
        await OmniBox.log(
            "info", "[好好看][category] tid=%s page=%s n=%s" % (tid, page, len(cards))
        )
        return {
            "list": cards,
            "page": page,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * max(len(cards), 1),
        }
    except Exception as e:
        await OmniBox.log("error", "[好好看][category] %s" % e)
        return {"list": [], "page": page, "pagecount": page, "total": 0}


async def search(params, context):
    key = str(
        (params or {}).get("keyword")
        or (params or {}).get("wd")
        or (params or {}).get("key")
        or ""
    ).strip()
    page = _page((params or {}).get("page") or 1)
    if not key:
        return {"list": [], "page": 1, "pagecount": 0, "total": 0}
    try:
        await _ensure_host()
        cards = []
        for url in _search_urls(key, page):
            st, text, _ = await _req(url)
            if not text or ("cdndefend" in text and len(text) < 2000):
                continue
            if "ajax/suggest" in url or text.strip().startswith("{"):
                try:
                    data = json.loads(text)
                    lst = data.get("list") or data.get("data") or []
                    for it in lst:
                        vid = str(it.get("id") or it.get("vod_id") or "")
                        name = str(it.get("name") or it.get("vod_name") or "")
                        if vid and name:
                            cards.append(
                                {
                                    "vod_id": vid,
                                    "vod_name": name,
                                    "vod_pic": _abs(it.get("pic") or it.get("vod_pic")),
                                    "vod_remarks": str(it.get("remarks") or ""),
                                }
                            )
                except Exception:
                    pass
            else:
                cards = _parse_cards(text)
            if cards:
                break
        return {
            "list": cards[:50],
            "page": page,
            "pagecount": page + (1 if len(cards) >= 15 else 0),
            "total": len(cards),
        }
    except Exception as e:
        await OmniBox.log("error", "[好好看][search] %s" % e)
        return {"list": [], "page": page, "pagecount": 0, "total": 0}


def _parse_play_sources(html, vid):
    sources = []
    from_m = re.search(
        r'(?:id|name)=["\']vod_play_from["\'][^>]*value=["\']([^"\']+)', html, re.I
    )
    url_m = re.search(
        r'(?:id|name)=["\']vod_play_url["\'][^>]*value=["\']([^"\']+)', html, re.I
    )
    if not from_m:
        from_m = re.search(r"vod_play_from\s*[:=]\s*[\"']([^\"']+)", html)
    if not url_m:
        url_m = re.search(r"vod_play_url\s*[:=]\s*[\"']([^\"']+)", html)

    if from_m and url_m:
        flags = from_m.group(1).split("$$$")
        groups = url_m.group(1).split("$$$")
        for i, flag in enumerate(flags):
            group = groups[i] if i < len(groups) else ""
            eps = []
            for j, part in enumerate(group.split("#")):
                part = part.strip()
                if not part:
                    continue
                if "$" in part:
                    name, u = part.split("$", 1)
                else:
                    name, u = "第%s集" % (j + 1), part
                if u.startswith("http"):
                    pid = "url|" + u
                else:
                    pid = "%s|%s|%s" % (vid, i + 1, j + 1)
                eps.append({"name": (name or ("第%s集" % (j + 1))).strip(), "playId": pid})
            if eps:
                sources.append({"name": flag.strip() or ("线路%s" % (i + 1)), "episodes": eps})

    if not sources:
        by_sid = {}
        for m in re.finditer(
            r'href="[^"]*?/vod/play/id/%s/sid/(\d+)/nid/(\d+)[^"]*"[^>]*>([^<]+)'
            % re.escape(str(vid)),
            html,
            re.I,
        ):
            sid, nid, name = m.group(1), m.group(2), m.group(3).strip()
            by_sid.setdefault(sid, []).append(
                {"name": name or ("第%s集" % nid), "playId": "%s|%s|%s" % (vid, sid, nid)}
            )
        for sid, eps in sorted(by_sid.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
            sources.append({"name": "线路%s" % sid, "episodes": eps})

    if not sources:
        sources.append(
            {"name": "默认", "episodes": [{"name": "播放", "playId": "%s|1|1" % vid}]}
        )
    return sources


async def detail(params, context):
    p = params or {}
    vid = str(
        p.get("videoId") or p.get("vodId") or p.get("id") or p.get("ids") or ""
    ).strip()
    if not vid:
        return {"list": []}
    try:
        await _ensure_host()
        html = await _get_html(_detail_urls(vid))
        title = ""
        tm = re.search(r"<h1[^>]*>\s*([^<]+)", html) or re.search(
            r'property="og:title"\s+content="([^"]+)"', html
        )
        if tm:
            title = tm.group(1).strip()
        pic = ""
        pm = re.search(r'property="og:image"\s+content="([^"]+)"', html)
        if pm:
            pic = _abs(pm.group(1))
        content = ""
        cm = re.search(
            r'class="[^"]*(?:txt|content|desc|sketch)[^"]*"[^>]*>([\s\S]{0,800}?)</div>',
            html,
            re.I,
        )
        if cm:
            content = re.sub(r"<[^>]+>", "", cm.group(1)).strip()
        sources = _parse_play_sources(html, vid)
        await OmniBox.log(
            "info", "[好好看][detail] id=%s sources=%s" % (vid, len(sources))
        )
        return {
            "list": [
                {
                    "vod_id": vid,
                    "vod_name": title or ("影片 %s" % vid),
                    "vod_pic": pic,
                    "vod_content": content,
                    "vod_play_sources": sources,
                }
            ]
        }
    except Exception as e:
        await OmniBox.log("error", "[好好看][detail] %s" % e)
        return {"list": []}


async def play(params, context):
    play_id = str((params or {}).get("playId") or (params or {}).get("id") or "").strip()
    headers = {"User-Agent": UA, "Referer": HOST + "/"}
    if not play_id:
        return {"urls": [], "parse": 0, "header": headers}
    try:
        await _ensure_host()
        if play_id.startswith("url|"):
            u = play_id[4:]
            parse = 0 if re.search(r"\.(m3u8|mp4)(\?|$)", u, re.I) else 1
            return {"urls": [{"name": "播放", "url": u}], "parse": parse, "header": headers}
        if play_id.startswith("http"):
            parse = 0 if re.search(r"\.(m3u8|mp4)(\?|$)", play_id, re.I) else 1
            return {
                "urls": [{"name": "播放", "url": play_id}],
                "parse": parse,
                "header": headers,
            }

        parts = play_id.split("|")
        vid = parts[0]
        sid = parts[1] if len(parts) > 1 else "1"
        nid = parts[2] if len(parts) > 2 else "1"
        play_urls = [
            "%s/index.php/vod/play/id/%s/sid/%s/nid/%s.html" % (HOST, vid, sid, nid),
            "%s/vod/play/id/%s/sid/%s/nid/%s.html" % (HOST, vid, sid, nid),
        ]
        html = await _get_html(play_urls)
        m = re.search(r"player_aaaa\s*=\s*(\{[\s\S]*?\})\s*;?\s*</script>", html)
        if not m:
            m = re.search(r"var\s+player_[a-zA-Z0-9]+\s*=\s*(\{[\s\S]*?\})\s*;", html)
        if m:
            try:
                info = json.loads(m.group(1))
                u = str(info.get("url") or "").strip()
                if u:
                    if info.get("encrypt") in (1, "1", 2, "2") and not u.startswith("http"):
                        try:
                            import base64
                            from urllib.parse import unquote

                            u2 = unquote(base64.b64decode(u).decode("utf-8", "ignore"))
                            if u2.startswith("http"):
                                u = u2
                        except Exception:
                            pass
                    u = _abs(u)
                    parse = 0 if re.search(r"\.(m3u8|mp4)(\?|$)", u, re.I) else int(
                        info.get("parse") or 0
                    )
                    return {
                        "urls": [{"name": "播放", "url": u}],
                        "parse": 0 if parse == 0 else 1,
                        "header": headers,
                    }
            except Exception as e:
                await OmniBox.log("warn", "[好好看][play] json %s" % e)

        mm = re.search(r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', html)
        if mm:
            return {
                "urls": [{"name": "播放", "url": mm.group(1)}],
                "parse": 0,
                "header": headers,
            }

        return {
            "urls": [{"name": "网页", "url": play_urls[0]}],
            "parse": 1,
            "header": headers,
        }
    except Exception as e:
        await OmniBox.log("error", "[好好看][play] %s" % e)
        return {"urls": [], "parse": 1, "header": headers}


run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
