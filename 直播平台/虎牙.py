# -*- coding: utf-8 -*-
# @name 虎牙直播
# @version 1.3.0
# @description 虎牙直播 OmniBox 源：列表官方接口；播放走 ottiptv 代理签名流（连续可播）
# @downloadURL https://raw.githubusercontent.com/becauseyour/yingshi/main/%E7%9B%B4%E6%92%AD%E5%B9%B3%E5%8F%B0/虎牙.py
import json
import re
from urllib.parse import quote

from spider_runner import OmniBox, run

HOST = "https://www.huya.com"
# 参考 https://live.ottiptv.cc/huya/{房间号} → 302 到 ctype=huya_adr 的 FLV
OTT_HUYA = "https://live.ottiptv.cc/huya/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

CLASSES = [
    {"type_id": "0", "type_name": "全部热门"},
    {"type_id": "1", "type_name": "网游竞技"},
    {"type_id": "2165", "type_name": "户外"},
    {"type_id": "1663", "type_name": "星秀"},
    {"type_id": "2135", "type_name": "一起看"},
    {"type_id": "2336", "type_name": "主机游戏"},
    {"type_id": "2793", "type_name": "美食"},
    {"type_id": "2168", "type_name": "交友"},
    {"type_id": "7601", "type_name": "二次元"},
    {"type_id": "1669", "type_name": "娱乐天地"},
]


def _page(v):
    try:
        return max(1, int(v))
    except (ValueError, TypeError):
        return 1


def _rid(params):
    p = params or {}
    for k in ("videoId", "vodId", "playId", "id", "ids"):
        v = str(p.get(k) or "").strip()
        if v:
            return v.split("|")[0].strip()
    return ""


async def _get_json(url, referer=HOST + "/"):
    res = await OmniBox.request(
        url,
        {
            "method": "GET",
            "headers": {
                "User-Agent": UA,
                "Referer": referer,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            "timeout": 12,
        },
    )
    status = int(res.get("statusCode") or 0)
    body = res.get("body")
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="ignore")
    text = str(body or "")
    if status and (status < 200 or status >= 400):
        raise IOError("HTTP %s" % status)
    if not text or text[:1] == "<":
        return {}
    return json.loads(text)


def _fmt_online(n):
    try:
        n = int(n)
    except Exception:
        return str(n or "")
    if n >= 10000:
        return "%.1f万" % (n / 10000)
    return str(n)


def _room_item(item):
    rid = str(item.get("profileRoom") or item.get("uid") or "").strip()
    if not rid:
        return None
    title = (item.get("introduction") or item.get("roomName") or item.get("nick") or "").strip()
    if not title:
        title = item.get("nick") or rid
    pic = item.get("screenshot") or item.get("avatar180") or ""
    if pic.startswith("//"):
        pic = "https:" + pic
    online = _fmt_online(item.get("totalCount") or item.get("aliveNum") or 0)
    game = item.get("gameFullName") or ""
    remark = "%s · %s" % (game, online) if game else online
    return {
        "vod_id": rid,
        "vod_name": title,
        "vod_pic": pic,
        "vod_remarks": remark,
    }


def _https(url):
    url = str(url or "").strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        return "https://" + url[7:]
    return url


def _build_streams(stream):
    """组装可播地址：优先 HLS（连续直播），FLV 备选。

    说明：部分端把 FLV 当点播，只缓冲一段就暂停；HLS(m3u8) 更适合一直看。
    TX 线路 HLS 兼容性通常最好。
    """
    if not isinstance(stream, dict):
        return []
    play_urls = []
    seen = set()

    def add(name, url):
        url = _https(url)
        if not url or url in seen:
            return
        path = url.split("?", 1)[0].lower()
        if not (path.endswith(".m3u8") or path.endswith(".flv") or ".m3u8" in path or ".flv" in path):
            return
        seen.add(url)
        play_urls.append({"name": name, "url": url})

    # 1) multiLine（常已带完整 anti 参数）
    for kind, label in (("hls", "HLS"), ("flv", "FLV")):
        block = stream.get(kind) or {}
        if not isinstance(block, dict):
            continue
        lines = block.get("multiLine") or []
        if isinstance(lines, dict):
            lines = [lines]
        for i, line in enumerate(lines):
            if not isinstance(line, dict):
                continue
            url = line.get("url") or line.get("sUrl") or line.get("playUrl") or ""
            cdn = str(line.get("cdnType") or line.get("sCdnType") or "")
            label_i = "%s%s%s" % (cdn + "-" if cdn else "", label, i + 1 if not cdn else "")
            if not cdn:
                label_i = "%s%s" % (label, i + 1)
            else:
                label_i = "%s-%s" % (cdn, label)
            if url:
                add(label_i, url)

    # 2) baseSteamInfoList 补全
    base_list = stream.get("baseSteamInfoList") or []
    if isinstance(base_list, dict):
        base_list = [base_list]
    for s in base_list:
        if not isinstance(s, dict):
            continue
        cdn = str(s.get("sCdnType") or "CDN")
        name = str(s.get("sStreamName") or "").strip()
        if not name:
            continue
        hls = s.get("sHlsUrl") or ""
        hls_suffix = s.get("sHlsUrlSuffix") or "m3u8"
        hls_anti = s.get("sHlsAntiCode") or s.get("sFlvAntiCode") or ""
        if hls:
            add("%s-HLS" % cdn, "%s/%s.%s?%s" % (hls.rstrip("/"), name, hls_suffix, hls_anti))
        flv = s.get("sFlvUrl") or ""
        flv_suffix = s.get("sFlvUrlSuffix") or "flv"
        flv_anti = s.get("sFlvAntiCode") or s.get("newCFlvAntiCode") or ""
        if flv:
            add("%s-FLV" % cdn, "%s/%s.%s?%s" % (flv.rstrip("/"), name, flv_suffix, flv_anti))

    def _score(item):
        n = (item.get("name") or "").upper()
        u = (item.get("url") or "").lower()
        # HLS 优先，TX 线路优先；FLV 垫后
        score = 0
        if "HLS" in n or ".m3u8" in u:
            score += 100
        if "TX" in n or "tx.hls" in u:
            score += 50
        if "AL" in n or "al.hls" in u:
            score += 20
        if "FLV" in n or ".flv" in u:
            score -= 40
        return -score

    play_urls.sort(key=_score)
    return play_urls[:8]


async def _profile(rid):
    url = "https://mp.huya.com/cache.php?m=Live&do=profileRoom&roomid=%s" % rid
    return await _get_json(url, referer=HOST + "/" + rid)


async def home(params, context):
    try:
        data = await _get_json(
            HOST + "/cache.php?m=LiveList&do=getLiveListByPage&tagAll=0&page=1"
        )
        datas = (data.get("data") or {}).get("datas") or []
        cards = []
        for it in datas[:48]:
            if int(it.get("totalCount") or 0) <= 0:
                continue
            card = _room_item(it)
            if card:
                cards.append(card)
        await OmniBox.log("info", "[虎牙][home] list=%s" % len(cards))
        return {"class": CLASSES, "list": cards}
    except Exception as e:
        await OmniBox.log("error", "[虎牙][home] %s" % e)
        return {"class": CLASSES, "list": []}


async def category(params, context):
    tid = str(
        (params or {}).get("categoryId")
        or (params or {}).get("type_id")
        or (params or {}).get("tid")
        or "0"
    )
    page = _page((params or {}).get("page") or (params or {}).get("pg") or 1)
    try:
        if tid == "0":
            url = HOST + "/cache.php?m=LiveList&do=getLiveListByPage&tagAll=0&page=%s" % page
        else:
            url = (
                HOST
                + "/cache.php?m=LiveList&do=getLiveListByPage&gameId=%s&tagAll=0&page=%s"
                % (tid, page)
            )
        data = await _get_json(url)
        d = data.get("data") or {}
        datas = d.get("datas") or []
        cards = []
        for it in datas:
            if int(it.get("totalCount") or 0) <= 0:
                continue
            card = _room_item(it)
            if card:
                cards.append(card)
        total_page = int(d.get("totalPage") or page)
        await OmniBox.log(
            "info", "[虎牙][category] tid=%s page=%s list=%s" % (tid, page, len(cards))
        )
        return {
            "list": cards,
            "page": page,
            "pagecount": max(total_page, page),
            "total": int(d.get("totalCount") or 0) or len(cards) * total_page,
        }
    except Exception as e:
        await OmniBox.log("error", "[虎牙][category] %s" % e)
        return {"list": [], "page": page, "pagecount": page, "total": 0}


async def search(params, context):
    keyword = str(
        (params or {}).get("keyword")
        or (params or {}).get("wd")
        or (params or {}).get("key")
        or ""
    ).strip()
    page = _page((params or {}).get("page") or (params or {}).get("pg") or 1)
    if not keyword:
        return {"list": [], "page": page, "pagecount": page, "total": 0}
    try:
        # 列表接口无可靠搜索时：热门里本地过滤 + 数字房号直达
        data = await _get_json(
            HOST + "/cache.php?m=LiveList&do=getLiveListByPage&tagAll=0&page=1"
        )
        datas = (data.get("data") or {}).get("datas") or []
        key_l = keyword.lower()
        cards = []
        for it in datas:
            card = _room_item(it)
            if not card:
                continue
            if key_l in (card["vod_name"] or "").lower() or key_l == card["vod_id"]:
                cards.append(card)
        if not cards and re.match(r"^\d+$", keyword):
            cards.append(
                {
                    "vod_id": keyword,
                    "vod_name": "虎牙直播间 %s" % keyword,
                    "vod_pic": "",
                    "vod_remarks": "直达",
                }
            )
        await OmniBox.log("info", "[虎牙][search] key=%s list=%s" % (keyword, len(cards)))
        return {
            "list": cards,
            "page": page,
            "pagecount": 1,
            "total": len(cards),
        }
    except Exception as e:
        await OmniBox.log("error", "[虎牙][search] %s" % e)
        return {"list": [], "page": page, "pagecount": page, "total": 0}


async def detail(params, context):
    rid = _rid(params)
    if not rid:
        return {"list": []}
    try:
        data = await _profile(rid)
        root = data.get("data") or {}
        live_status = str(root.get("liveStatus") or root.get("realLiveStatus") or "").upper()
        info = root.get("liveData") or root.get("profileInfo") or {}
        title = (
            info.get("introduction")
            or info.get("roomName")
            or info.get("nick")
            or ("虎牙直播间 %s" % rid)
        )
        pic = info.get("screenshot") or info.get("avatarUrl") or info.get("avatar180") or ""
        pic = _https(pic)
        online = _fmt_online(info.get("totalCount") or info.get("online") or 0)
        game = info.get("gameFullName") or info.get("gameName") or ""
        owner = info.get("nick") or info.get("ownerName") or ""
        is_live = live_status in ("ON", "1", "LIVE", "2") or int(
            info.get("totalCount") or 0
        ) > 0
        # 有流就当在播
        streams = _build_streams(root.get("stream") or {})
        if streams:
            is_live = True
        episodes = [{"name": "直播中", "playId": rid}] if is_live else []
        await OmniBox.log(
            "info", "[虎牙][detail] rid=%s live=%s streams=%s" % (rid, is_live, len(streams))
        )
        return {
            "list": [
                {
                    "vod_id": rid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ("%s · %s" % (game, online)).strip(" ·"),
                    "vod_actor": owner,
                    "vod_content": "主播: %s\n分区: %s\n人气: %s" % (owner, game, online),
                    "vod_play_sources": [{"name": "虎牙直播", "episodes": episodes}],
                }
            ]
        }
    except Exception as e:
        await OmniBox.log("error", "[虎牙][detail] %s" % e)
        # 兜底仍给播放入口，避免“点不进去”
        return {
            "list": [
                {
                    "vod_id": rid,
                    "vod_name": "虎牙直播间 %s" % rid,
                    "vod_pic": "",
                    "vod_remarks": "",
                    "vod_play_sources": [
                        {"name": "虎牙直播", "episodes": [{"name": "直播", "playId": rid}]}
                    ],
                }
            ]
        }


async def _resolve_ott(rid):
    """解析 live.ottiptv.cc/huya/{rid} 的 302，得到带 huya_adr 签名的 FLV。"""
    proxy = OTT_HUYA + str(rid)
    try:
        res = await OmniBox.request(
            proxy,
            {
                "method": "GET",
                "headers": {
                    "User-Agent": UA,
                    "Accept": "*/*",
                    "Referer": "https://live.ottiptv.cc/",
                },
                "timeout": 12,
                # 若 SDK 支持关闭跟随，拿到 Location；不支持则用最终 url/body 判断
                "redirect": "manual",
            },
        )
    except Exception as e:
        await OmniBox.log("warn", "[虎牙][ott] request fail %s" % e)
        return proxy, ""

    headers = res.get("headers") or res.get("header") or {}
    if not isinstance(headers, dict):
        headers = {}
    # 兼容大小写
    loc = (
        headers.get("Location")
        or headers.get("location")
        or headers.get("LOCATION")
        or ""
    )
    if not loc and isinstance(res.get("responseHeaders"), dict):
        rh = res["responseHeaders"]
        loc = rh.get("Location") or rh.get("location") or ""
    final_url = str(res.get("url") or res.get("finalUrl") or "").strip()
    status = int(res.get("statusCode") or 0)
    body = res.get("body")
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="ignore")
    text = str(body or "")

    # 302 Location
    if loc and (".flv" in loc or "huya.com" in loc):
        return proxy, _https(loc)
    # 已跟随重定向到 flv
    if final_url and ".flv" in final_url and "huya.com" in final_url:
        return proxy, _https(final_url)
    # 响应体是 FLV 魔数时说明已拿到流（但无 URL），仍返回 proxy 让播放器自己跟
    if text[:3] == "FLV" or status == 200:
        return proxy, ""
    # HTML 里偶发带 location
    m = re.search(r'https?://[^"\'\s]+huya\.com[^"\'\s]+\.flv[^"\'\s]*', text)
    if m:
        return proxy, _https(m.group(0))
    return proxy, ""


async def play(params, context):
    rid = _rid(params)
    if not rid:
        return {"urls": [], "parse": 0, "header": {}}
    headers = {
        "User-Agent": UA,
        "Referer": "https://www.huya.com/",
        "Origin": "https://www.huya.com",
    }
    try:
        urls = []
        proxy, direct = await _resolve_ott(rid)
        if direct:
            urls.append({"name": "OTT直链", "url": direct})
            await OmniBox.log("info", "[虎牙][play] ott direct ok rid=%s" % rid)
        # 代理地址本身可播（播放器跟 302），放前面优先
        urls.insert(0, {"name": "OTT代理", "url": proxy})

        # 官方 profile 作备用线路
        try:
            data = await _profile(rid)
            root = data.get("data") or {}
            native = _build_streams(root.get("stream") or {})
            for it in native[:4]:
                if not any(x.get("url") == it.get("url") for x in urls):
                    urls.append(it)
        except Exception as e:
            await OmniBox.log("warn", "[虎牙][play] native %s" % e)

        if urls:
            return {
                "urls": urls,
                "parse": 0,
                "header": headers,
                "extra": {"live": True},
            }

        return {
            "urls": [{"name": "OTT代理", "url": OTT_HUYA + rid}],
            "parse": 0,
            "header": headers,
            "extra": {"live": True},
        }
    except Exception as e:
        await OmniBox.log("error", "[虎牙][play] %s" % e)
        return {
            "urls": [{"name": "OTT代理", "url": OTT_HUYA + rid}],
            "parse": 0,
            "header": headers,
            "extra": {"live": True},
        }


run({"home": home, "category": category, "detail": detail, "search": search, "play": play})
