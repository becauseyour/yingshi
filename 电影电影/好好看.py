# -*- coding: utf-8 -*-
# @name 好好看
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%94%B5%E5%BD%B1%E7%94%B5%E8%A7%86/好好看.py
# @description 好好看影视（hhkan 多镜像）：列表/搜索/详情/播放，自动切换可用官网

"""
好好看 — OmniBox v1.0.0

最新官网镜像:
  www.hhkan1.com / www.hhkan2.com / www.hhkan3.com / www.hhkan4.com
说明:
  - 自动探测可用域名并缓存
  - 分类: 电影 / 剧集 / 综艺 / 动漫 / 短剧（按站内 id，失败时仍可搜索）
  - 播放优先解析 player_aaaa → m3u8/mp4；否则回落网页 parse=1
  - 若遇 CDN 人机验证，请在可打开官网的网络下使用
"""

import json
import re
import time
from urllib.parse import quote, urljoin

from spider_runner import OmniBox, run

HOSTS = [
    "https://www.hhkan1.com",
    "https://www.hhkan2.com",
    "https://www.hhkan3.com",
    "https://www.hhkan4.com",
    "https://www.hhkan0.com",
]
HOST = HOSTS[0]
UA = (
    "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
)

# 常见 MacCMS 分类 id（站点若不同会在 home 时尝试校正）
CLASSES = [
    {"type_id": "1", "type_name": "电影"},
    {"type_id": "2", "type_name": "剧集"},
    {"type_id": "3", "type_name": "综艺"},
    {"type_id": "4", "type_name": "动漫"},
    {"type_id": "5", "type_name": "短剧"},
]


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
    """轮询镜像，选一个能返回正常页面的。"""
    global HOST
    cache_key = "hhkan_host_v1"
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
            # CDN 人机验证页通常很短且含 cdndefend / verifying
            if st and st >= 400:
                continue
            if "cdndefend" in text or "verifying your browser" in text.lower():
                continue
            if len(text) < 800:
                continue
            HOST = h if "hhkan" in final else final.rstrip("/")
            # 若跳到别的 hhkan 域名也接受
            m = re.search(r"https?://(?:www\.)?hhkan\d*\.com", final)
            if m:
                HOST = m.group(0)
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
    """从列表页提取影片卡片。"""
    cards = []
    seen = set()
    # 链到 detail 的条目
    for m in re.finditer(
        r'href="((?:https?://[^"]+)?/(?:index\.php/)?vod/(?:detail|play)/id/(\d+)[^"]*)"[^>]*>',
        html,
        re.I,
    ):
        href, vid = m.group(1), m.group(2)
        if vid in seen:
            continue
        # 向后看一小段取标题和图片
        tail = html[m.end() : m.end() + 400]
        title = ""
        tm = re.search(r'title="([^"]+)"', tail) or re.search(
            r"<h\d[^>]*>\s*([^<]+)", tail
        )
        if tm:
            title = tm.group(1).strip()
        if not title:
            tm = re.search(r'alt="([^"]+)"', tail)
            if tm:
                title = tm.group(1).strip()
        pic = ""
        pm = re.search(
            r'(?:data-original|data-src|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)',
            tail,
            re.I,
        )
        if pm:
            pic = pm.group(1)
        remarks = ""
        rm = re.search(
            r'class="[^"]*(?:pic-text|text-right|remarks|v_note)[^"]*"[^>]*>([^<]+)',
            tail,
            re.I,
        )
        if rm:
            remarks = rm.group(1).strip()
        if not title:
            continue
        seen.add(vid)
        cards.append(
            {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": _abs(pic),
                "vod_remarks": remarks,
            }
        )
    # 补充：mac 主题 module-item
    if len(cards) < 5:
        for m in re.finditer(
            r'class="[^"]*module-item[^"]*"[\s\S]{0,600}?href="[^"]*?/id/(\d+)[^"]*"[\s\S]{0,400}?alt="([^"]+)"',
            html,
            re.I,
        ):
            vid, title = m.group(1), m.group(2).strip()
            if vid in seen or not title:
                continue
            seen.add(vid)
            block = m.group(0)
            pic = ""
            pm = re.search(
                r'(?:data-original|data-src|src)=["\']([^"\']+)', block, re.I
            )
            if pm:
                pic = pm.group(1)
            cards.append(
                {
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": _abs(pic),
                    "vod_remarks": "",
                }
            )
    return cards


def _list_url(tid, page):
    # 多种常见路径，_get_list 里依次尝试
    return [
        "%s/index.php/vod/show/id/%s/page/%s.html" % (HOST, tid, page),
        "%s/vod/show/id/%s/page/%s.html" % (HOST, tid, page),
        "%s/index.php/vodtype/%s-%s.html" % (HOST, tid, page),
        "%s/vodtype/%s-%s.html" % (HOST, tid, page),
        "%s/index.php/vod/type/id/%s/page/%s.html" % (HOST, tid, page),
    ]


def _search_url(keyword, page):
    q = quote(keyword)
    return [
        "%s/index.php/vod/search/page/%s/wd/%s.html" % (HOST, page, q),
        "%s/vod/search/page/%s/wd/%s.html" % (HOST, page, q),
        "%s/index.php/vod/search/wd/%s/page/%s.html" % (HOST, q, page),
        "%s/index.php/ajax/suggest?mid=1&wd=%s&limit=20" % (HOST, q),
    ]


def _detail_url(vid):
    return [
        "%s/index.php/vod/detail/id/%s.html" % (HOST, vid),
        "%s/vod/detail/id/%s.html" % (HOST, vid),
        "%s/index.php/vod/play/id/%s/sid/1/nid/1.html" % (HOST, vid),
    ]


async def _get_html(urls):
    last = ""
    for url in urls:
        try:
            st, text, _ = await _req(url)
            if "cdndefend" in text or "verifying your browser" in text.lower():
                last = text
                continue
            if st and st >= 400:
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
        html = await _get_html([HOST + "/", HOST + "/index.php"])
        cards = _parse_cards(html)[:48]
        await OmniBox.log("info", "[好好看][home] host=%s n=%s" % (HOST, len(cards)))
        return {"class": CLASSES, "list": cards, "filters": {}}
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
        html = await _get_html(_list_url(tid, page))
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
        for url in _search_url(key, page):
            st, text, _ = await _req(url)
            if not text or "cdndefend" in text:
                continue
            # suggest json
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
    """解析详情页线路与剧集。"""
    sources = []
    # 1) 经典 MacCMS: vod_play_from / vod_play_url 隐域
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
                eps.append(
                    {
                        "name": name.strip() or ("第%s集" % (j + 1)),
                        "playId": "%s|%s|%s" % (vid, i + 1, j + 1)
                        if not u.startswith("http")
                        else u,
                    }
                )
                # 直链写进 playId 前缀 url:
                if u.startswith("http"):
                    eps[-1]["playId"] = "url|" + u
            if eps:
                sources.append({"name": flag.strip() or ("线路%s" % (i + 1)), "episodes": eps})

    # 2) 播放列表链接 /vod/play/id/xx/sid/a/nid/b
    if not sources:
        by_sid = {}
        for m in re.finditer(
            r'href="((?:https?://[^"]+)?/(?:index\.php/)?vod/play/id/%s/sid/(\d+)/nid/(\d+)[^"]*)"[^>]*>([^<]+)'
            % re.escape(str(vid)),
            html,
            re.I,
        ):
            sid, nid, name = m.group(2), m.group(3), m.group(4).strip()
            by_sid.setdefault(sid, []).append(
                {"name": name or ("第%s集" % nid), "playId": "%s|%s|%s" % (vid, sid, nid)}
            )
        for sid, eps in sorted(by_sid.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
            sources.append({"name": "线路%s" % sid, "episodes": eps})

    if not sources:
        sources.append(
            {
                "name": "默认",
                "episodes": [{"name": "播放", "playId": "%s|1|1" % vid}],
            }
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
        html = await _get_html(_detail_url(vid))
        title = ""
        tm = re.search(r"<h1[^>]*>\s*([^<]+)", html) or re.search(
            r'property="og:title"\s+content="([^"]+)"', html
        )
        if tm:
            title = tm.group(1).strip()
        pic = ""
        pm = re.search(
            r'property="og:image"\s+content="([^"]+)"', html
        ) or re.search(
            r'class="[^"]*(?:detail|vod)[^"]*"[^>]*>[\s\S]{0,200}?(?:data-original|src)="([^"]+)"',
            html,
            re.I,
        )
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
    play_id = str(
        (params or {}).get("playId")
        or (params or {}).get("id")
        or ""
    ).strip()
    headers = {"User-Agent": UA, "Referer": HOST + "/"}
    if not play_id:
        return {"urls": [], "parse": 0, "header": headers}
    try:
        await _ensure_host()
        # url|https://...
        if play_id.startswith("url|"):
            u = play_id[4:]
            parse = 0 if re.search(r"\.(m3u8|mp4)(\?|$)", u, re.I) else 1
            return {
                "urls": [{"name": "播放", "url": u}],
                "parse": parse,
                "header": headers,
            }
        # 直链
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
        # player_aaaa
        m = re.search(r"player_aaaa\s*=\s*(\{[\s\S]*?\})\s*;?\s*</script>", html)
        if not m:
            m = re.search(r"var\s+player_[a-zA-Z0-9]+\s*=\s*(\{[\s\S]*?\})\s*;", html)
        if m:
            try:
                info = json.loads(m.group(1))
                u = str(info.get("url") or "").strip()
                if u:
                    # url 可能 base64
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
                    await OmniBox.log("info", "[好好看][play] got url parse=%s" % parse)
                    return {
                        "urls": [{"name": "播放", "url": u}],
                        "parse": parse if parse in (0, 1) else 0,
                        "header": headers,
                    }
            except Exception as e:
                await OmniBox.log("warn", "[好好看][play] json %s" % e)

        # 页面内 m3u8
        mm = re.search(r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', html)
        if mm:
            return {
                "urls": [{"name": "播放", "url": mm.group(1)}],
                "parse": 0,
                "header": headers,
            }

        # 回落播放页
        return {
            "urls": [{"name": "网页", "url": play_urls[0]}],
            "parse": 1,
            "header": headers,
        }
    except Exception as e:
        await OmniBox.log("error", "[好好看][play] %s" % e)
        return {"urls": [], "parse": 1, "header": headers}


run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
