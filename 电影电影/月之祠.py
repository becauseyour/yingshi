# -*- coding: utf-8 -*-
# @name 月之祠
# @version 1.0.0
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%94%B5%E5%BD%B1%E7%94%B5%E8%A7%86/%E6%9C%88%E4%B9%8B%E7%A5%A0.py
# @description moonci.com 二次元番剧；OmniBox vod_play_sources

import json
import re
from urllib.parse import quote, unquote, urljoin

from spider_runner import OmniBox, run

HOST = "https://www.moonci.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": HOST + "/",
}
CLASSES = [
    {"type_id": "20", "type_name": "新番"},
    {"type_id": "21", "type_name": "番剧"},
    {"type_id": "22", "type_name": "剧场"},
]
PER_PAGE = 36


def _to_int(v, default=0):
    try:
        return int(float(v)) if isinstance(v, str) else int(v)
    except (ValueError, TypeError):
        return default


def _clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def _abs(url):
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return HOST + url
    if not url.startswith("http"):
        return urljoin(HOST + "/", url)
    return url


async def _fetch(url, referer=None):
    headers = dict(HEADERS)
    if referer:
        headers["Referer"] = referer
    res = await OmniBox.request(url, {"method": "GET", "headers": headers, "timeout": 15})
    return res.get("body") or ""


def _browse_url(tid, letter="", by="", page=1):
    segs = [""] * 12
    if by:
        segs[2] = by
    if letter:
        segs[5] = letter
    if page and int(page) > 1:
        segs[8] = str(int(page))
    return "%s/browse/%s%s.html" % (HOST, tid, "-".join(segs))


def _search_url(key, page=1):
    segs = [""] * 14
    segs[0] = quote(key)
    if page and int(page) > 1:
        segs[10] = str(int(page))
    return "%s/search/%s.html" % (HOST, "-".join(segs))


def _parse_cards(html):
    items, seen = [], set()
    if not html or len(html) < 600:
        return items
    for m in re.finditer(
        r'<li[^>]*class="[^"]*hl-list-item[^"]*"[\s\S]*?</li>', html, re.I
    ):
        block = m.group(0)
        hm = re.search(r'href="(/anime/(\d+)\.html)"', block)
        if not hm:
            continue
        vod_id = hm.group(2)
        if vod_id in seen:
            continue
        seen.add(vod_id)
        tm = re.search(r'title="([^"]+)"', block)
        title = _clean(tm.group(1) if tm else "")
        if not title:
            im = re.search(r'alt="([^"]+)"', block)
            title = _clean(im.group(1) if im else vod_id)
        pm = re.search(
            r'(?:data-original|data-src|src)="(https?://[^"]+|//[^"]+|/[^"]+)"', block
        )
        pic = _abs(pm.group(1) if pm else "")
        remarks = ""
        for rm in re.finditer(
            r'class="[^"]*(?:hl-pic-text|hl-vod-subtitle|hl-remarks|hl-item-text)[^"]*"[^>]*>([^<]+)',
            block,
        ):
            remarks = _clean(rm.group(1))
            if remarks:
                break
        items.append(
            {
                "vod_id": vod_id,
                "vod_name": title[:120],
                "vod_pic": pic,
                "vod_remarks": remarks,
            }
        )
    if not items:
        for hm in re.finditer(r'href="/anime/(\d+)\.html"[^>]*title="([^"]*)"', html):
            vod_id, title = hm.group(1), _clean(hm.group(2))
            if vod_id in seen:
                continue
            seen.add(vod_id)
            items.append(
                {
                    "vod_id": vod_id,
                    "vod_name": title or vod_id,
                    "vod_pic": "",
                    "vod_remarks": "",
                }
            )
    return items


def _pagecount(html, marker):
    if not html:
        return 1
    nums = [
        int(x)
        for x in re.findall(
            r'href="[^"]*%s[^"]*"[^>]*>(\d+)</a>' % re.escape(marker), html
        )
    ]
    return max(nums) if nums else 1


def _info(html, *labels):
    for label in labels:
        m = re.search(
            re.escape(label)
            + r"[：:][^<]*</em>([\s\S]*?)(?:</li>|</p>|</div>|</span>)",
            html,
            re.S,
        )
        if m:
            val = re.sub(r"<[^>]+>", " ", m.group(1))
            val = re.sub(r"\s+", " ", val.replace("&nbsp;", " ")).strip(" /")
            if val and val not in ("内详", "未知", "暂无"):
                return val
    return ""


def _decode_player_url(data):
    raw = (data.get("url") or "").replace("\\/", "/")
    if not raw:
        return ""
    def _u(s):
        return re.sub(
            r"%u([0-9a-fA-F]{4})",
            lambda m: chr(int(m.group(1), 16)),
            s,
        )
    enc = str(data.get("encrypt", 0))
    if enc == "1":
        return unquote(_u(raw))
    if enc == "2":
        try:
            import base64
            return unquote(_u(base64.b64decode(raw).decode("utf-8", "ignore")))
        except Exception:
            return unquote(_u(raw))
    return _u(raw)


async def home(params, context):
    try:
        html = await _fetch(HOST + "/")
        return {"class": CLASSES, "list": _parse_cards(html), "filters": {}}
    except Exception as e:
        await OmniBox.log("error", "[home] %s" % e)
        return {"class": CLASSES, "list": [], "filters": {}}


async def category(params, context):
    tid = str((params or {}).get("categoryId") or "20")
    page = _to_int((params or {}).get("page"), 1) or 1
    try:
        # 优先 type 路径；browse 作筛选备用
        if page <= 1:
            url = "%s/type/%s.html" % (HOST, tid)
        else:
            url = "%s/type/%s/page/%s.html" % (HOST, tid, page)
        html = await _fetch(url)
        if not html or len(html) < 800:
            url = _browse_url(tid, page=page)
            html = await _fetch(url)
        items = _parse_cards(html)
        pagecount = max(_pagecount(html, "/type/%s" % tid), page)
        if pagecount == 1 and len(items) >= PER_PAGE // 2:
            pagecount = page + 1
        return {
            "list": items,
            "page": page,
            "pagecount": pagecount,
            "limit": PER_PAGE,
            "total": pagecount * PER_PAGE,
        }
    except Exception as e:
        await OmniBox.log("error", "[category] %s" % e)
        return {"list": [], "page": 1, "pagecount": 0, "limit": PER_PAGE, "total": 0}


async def detail(params, context):
    vid = str((params or {}).get("videoId") or "").strip()
    m = re.search(r"(\d+)", vid)
    vid = m.group(1) if m else vid
    if not vid:
        return {"list": []}
    try:
        html = await _fetch("%s/anime/%s.html" % (HOST, vid))
        if not html:
            return {"list": []}
        tm = re.search(r"<title>(.*?)(?:_|-|—|\|)", html)
        name = _clean(tm.group(1) if tm else "")
        name2 = _info(html, "片名")
        if name2:
            name = name2
        pm = re.search(r'data-original="(https?://[^"]+)"', html) or re.search(
            r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html
        )
        pic = _abs(pm.group(1) if pm else "")

        lines = {}
        for li in re.finditer(
            r'data-href="/anime/%s/play/(\d+)-1\.html"[^>]*>(.*?)</li>' % re.escape(vid),
            html,
            re.S,
        ):
            sid = int(li.group(1))
            block = li.group(2)
            nm = re.search(r">([^<]{1,12})</", block)
            lines[sid] = _clean(nm.group(1)) if nm else ("线路%s" % sid)

        eps = {}
        seen = set()
        for a in re.finditer(
            r'href="/anime/%s/play/(\d+)-(\d+)\.html"[^>]*>(.*?)</a>' % re.escape(vid),
            html,
        ):
            sid, nid = int(a.group(1)), int(a.group(2))
            if (sid, nid) in seen:
                continue
            seen.add((sid, nid))
            ep_name = re.sub(r"<[^>]+>", "", a.group(3)).replace("&nbsp;", " ").strip()
            if not re.search(r"第\s*\d+\s*集", ep_name):
                ep_name = "第%02d集" % nid
            play_id = "%s-%s-%s" % (vid, sid, nid)
            eps.setdefault(sid, {})[nid] = (ep_name, play_id)

        sources = []
        sids = sorted(lines.keys()) if lines else sorted(eps.keys())
        for sid in sids:
            segs = eps.get(sid) or {}
            if not segs:
                continue
            episodes = [
                {"name": n, "playId": pid}
                for _, (n, pid) in sorted(segs.items(), key=lambda kv: kv[0])
            ]
            sources.append(
                {"name": lines.get(sid) or ("线路%s" % sid), "episodes": episodes}
            )
        if not sources:
            sources = [
                {
                    "name": "默认",
                    "episodes": [{"name": "第01集", "playId": "%s-1-1" % vid}],
                }
            ]

        vod = {
            "vod_id": vid,
            "vod_name": name or vid,
            "vod_pic": pic,
            "vod_actor": _info(html, "主演"),
            "vod_director": _info(html, "导演"),
            "vod_year": _info(html, "年份"),
            "vod_area": _info(html, "地区"),
            "vod_lang": _info(html, "语言"),
            "type_name": _info(html, "类型"),
            "vod_remarks": _info(html, "状态", "更新"),
            "vod_content": _info(html, "简介"),
            "vod_play_sources": sources,
        }
        return {"list": [vod]}
    except Exception as e:
        await OmniBox.log("error", "[detail] %s" % e)
        return {"list": []}


async def search(params, context):
    key = str((params or {}).get("keyword") or "").strip()
    page = _to_int((params or {}).get("page"), 1) or 1
    if not key:
        return {"list": []}
    try:
        html = await _fetch(_search_url(key, page))
        items = _parse_cards(html)
        pagecount = max(_pagecount(html, "/search/"), page)
        return {"list": items, "page": page, "pagecount": pagecount}
    except Exception as e:
        await OmniBox.log("error", "[search] %s" % e)
        return {"list": []}


async def play(params, context):
    play_id = str(
        (params or {}).get("playId")
        or (params or {}).get("url")
        or (params or {}).get("id")
        or ""
    ).strip()
    headers = {"User-Agent": UA}  # 部分 CDN 带 Referer 会 400
    if not play_id:
        return {"urls": [], "parse": 0, "header": headers}

    if play_id.startswith("http") and re.search(r"\.(m3u8|mp4)(\?|$)", play_id, re.I):
        return {"urls": [{"name": "播放", "url": play_id}], "parse": 0, "header": headers}

    m = re.search(r"(\d+)-(\d+)-(\d+)", play_id)
    if m:
        page_url = "%s/anime/%s/play/%s-%s.html" % (
            HOST,
            m.group(1),
            m.group(2),
            m.group(3),
        )
    elif play_id.startswith("http"):
        page_url = play_id
    else:
        return {"urls": [], "parse": 0, "header": headers}

    try:
        html = await _fetch(page_url, referer=HOST + "/")
        data = None
        mm = re.search(
            r"var\s+player_aaaa\s*=\s*(\{.*?\});?\s*</script>", html or "", re.S
        )
        if mm:
            try:
                data = json.loads(mm.group(1))
            except Exception:
                data = None
        if data:
            real = _decode_player_url(data)
            real = _abs(real)
            if real and re.search(r"\.(m3u8|mp4)(\?|$)", real, re.I):
                return {
                    "urls": [{"name": "播放", "url": real}],
                    "parse": 0,
                    "header": headers,
                }
            if real.startswith("http"):
                # 中转页：交给客户端嗅探
                return {
                    "urls": [{"name": "线路", "url": real}],
                    "parse": 1,
                    "header": headers,
                }
        return {
            "urls": [{"name": "播放页", "url": page_url}],
            "parse": 1,
            "header": headers,
        }
    except Exception as e:
        await OmniBox.log("error", "[play] %s" % e)
        return {
            "urls": [{"name": "播放页", "url": page_url}],
            "parse": 1,
            "header": headers,
        }


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
