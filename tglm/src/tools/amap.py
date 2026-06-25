"""高德地图工具 - V5 API

工具列表：
- geocode: 地址 → 经纬度（V3 geo 接口，V5 仍兼容）
- reverse_geocode: 经纬度 → 城市名（V3 regeo 接口）
- get_citycode: 城市名 → citycode（V3 district 接口，供 V5 transit 用）
- transit_route: 公交/地铁路线规划（V5 transit/integrated）
- walking_route: 步行路线规划（V5 walking）

V5 关键规范（参照官方文档）：
1. transit/integrated 的 city1/city2 参数必须是 citycode（4位数字），不是城市名
2. city1 == city2 表示同城，不同则跨城
3. show_fields=cost 控制返回 cost 对象（含 duration/taxi_fee/transit_fee）
4. transit_fee 在 segments 下返回，taxi_fee 在 route.cost 下返回
5. AlternativeRoute 控制备选方案条数（1-10）
6. strategy 0-8（0=推荐 1=最经济 2=最少换乘 3=最少步行 4=最舒适 5=不乘地铁 6=地铁图 7=地铁优先 8=时间短）
"""
from __future__ import annotations

import httpx
from langchain_core.tools import tool

from ..config import settings
from ..logging_setup import get_logger

logger = get_logger(__name__)

AMAP_BASE = "https://restapi.amap.com"

# V5 transit 通过 show_fields 显式声明返回字段
_TRANSIT_SHOW_FIELDS = "cost"  # 包含 duration / taxi_fee / transit_fee

# 城市名 → citycode 内存缓存（一次会话内避免重复查询）
_CITYCODE_CACHE: dict[str, str] = {}


@tool
async def geocode(address: str) -> dict:
    """将地址文本转为经纬度（V3 geocode 接口，V5 兼容）。

    Args:
        address: 地址文本，例如 "杭州电子科技大学研究生公寓"

    Returns:
        成功：{longitude, latitude, city, formatted}
        失败：{error: str}
    """
    logger.info("tool_call", tool="geocode", address=address)
    if not settings.AMAP_KEY or settings.AMAP_KEY.startswith("your_"):
        logger.warning("amap_mock_mode", reason="AMAP_KEY not configured")
        return _mock_geocode(address)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{AMAP_BASE}/v3/geocode/geo", params={
                "key": settings.AMAP_KEY,
                "address": address,
            })
        data = r.json()
    except Exception as e:
        logger.error("geocode_http_failed", error=str(e))
        return {"error": f"geocode request failed: {e}"}

    if data.get("status") != "1" or not data.get("geocodes"):
        logger.warning("geocode_empty", address=address,
                       status=data.get("status"), info=data.get("info"))
        return {"error": f"geocode failed for {address}: {data.get('info')}"}

    g = data["geocodes"][0]
    try:
        lng, lat = g["location"].split(",")
    except (KeyError, ValueError):
        return {"error": f"unexpected geocode format: {g}"}

    city = g.get("city") or g.get("province") or ""
    if isinstance(city, list):
        city = city[0] if city else ""

    result = {
        "longitude": float(lng),
        "latitude": float(lat),
        "city": city,
        "formatted": g.get("formatted_address", address),
    }
    logger.info("tool_done", tool="geocode", result=result)
    return result


@tool
async def reverse_geocode(longitude: float, latitude: float) -> str:
    """根据经纬度反查城市名（V3 regeo 接口）。

    Args:
        longitude: 经度
        latitude: 纬度

    Returns:
        城市名字符串。失败返回空字符串。
    """
    logger.info("tool_call", tool="reverse_geocode",
                longitude=longitude, latitude=latitude)
    if not settings.AMAP_KEY or settings.AMAP_KEY.startswith("your_"):
        return _mock_reverse_geocode(longitude, latitude)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{AMAP_BASE}/v3/geocode/regeo", params={
                "key": settings.AMAP_KEY,
                "location": f"{longitude},{latitude}",
                "extensions": "base",
            })
        data = r.json()
    except Exception as e:
        logger.error("reverse_geocode_http_failed", error=str(e))
        return ""

    if data.get("status") != "1":
        logger.warning("reverse_geocode_failed", info=data.get("info"))
        return ""

    addr = data.get("regeocode", {}).get("addressComponent", {})
    city = addr.get("city") or addr.get("province") or ""
    if isinstance(city, list):
        city = city[0] if city else ""
    if not city:
        city = ""
    logger.info("tool_done", tool="reverse_geocode", city=city)
    return city


@tool
async def get_citycode(city_name: str) -> str:
    """根据城市名查询高德 citycode（V3 district 接口）。

    V5 公交路径规划接口要求 city1/city2 传 citycode 而非城市名。
    本工具封装了 district 查询，并对结果做进程内缓存避免重复请求。

    Args:
        city_name: 城市名，例如 "杭州" / "杭州市" / "宁波"

    Returns:
        citycode 字符串（如 "0571"）。失败返回原城市名（让上游 API 自己报错）。
    """
    if not city_name:
        return ""

    # 已经是 citycode（纯数字）就直接返回
    s = str(city_name).strip()
    if s.isdigit():
        return s

    # 标准化 key（去掉 "市/区/县" 后缀）
    cache_key = _normalize_city_key(s)
    if cache_key in _CITYCODE_CACHE:
        logger.info("citycode_cache_hit", city=city_name,
                    code=_CITYCODE_CACHE[cache_key])
        return _CITYCODE_CACHE[cache_key]

    logger.info("tool_call", tool="get_citycode", city=city_name)

    # mock 模式：维护一份小映射表
    if not settings.AMAP_KEY or settings.AMAP_KEY.startswith("your_"):
        code = _MOCK_CITYCODE.get(cache_key) or _MOCK_CITYCODE.get(s)
        if code:
            _CITYCODE_CACHE[cache_key] = code
            return code
        return s

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{AMAP_BASE}/v3/config/district", params={
                "key": settings.AMAP_KEY,
                "keywords": s,
                "subdistrict": "0",       # 不返回下级行政区，我们只要 citycode
                "extensions": "base",
            })
        data = r.json()
    except Exception as e:
        logger.error("get_citycode_http_failed", error=str(e))
        return s

    if data.get("status") != "1":
        logger.warning("get_citycode_failed", info=data.get("info"))
        return s

    districts = data.get("districts") or []
    if not districts:
        return s

    # 取第一个 district 的 citycode
    d = districts[0]
    code = d.get("citycode") or ""
    # citycode 为空字符串时（直辖市/特别区域），尝试用 adcode 前 4 位
    if not code or code == "0":
        adcode = d.get("adcode") or ""
        if len(adcode) >= 4:
            code = adcode[:4] + "00"  # 兜底，部分场景用 adcode 也能跑

    if code:
        _CITYCODE_CACHE[cache_key] = code
        logger.info("tool_done", tool="get_citycode",
                    city=city_name, code=code)
        return code
    return s


@tool
async def transit_route(
    origin: str,
    destination: str,
    city1: str,
    city2: str,
    strategy: int = 0,
    alternative_route: int = 3,
) -> dict:
    """公交/地铁路线规划（V5 transit/integrated 接口）。

    V5 关键规范：
      - city1 / city2 必须传 citycode（4位数字），不能传城市名
      - city1 == city2 表示同城，不同则跨城
      - 通过 show_fields=cost 返回 cost 对象（duration / taxi_fee）
      - transit_fee 在 segments 下返回（不在 transit.cost 里）

    Args:
        origin: 起点经纬度字符串，格式 "lng,lat"
        destination: 终点经纬度字符串，格式 "lng,lat"
        city1: 起点城市 citycode（如 "0571"）。可由 get_citycode 工具获得。
        city2: 终点城市 citycode。
        strategy: 公交换乘策略，0-8。
            0=推荐 1=最经济 2=最少换乘 3=最少步行
            4=最舒适 5=不乘地铁 6=地铁图 7=地铁优先 8=时间短
        alternative_route: 备选方案条数，1-10。默认 3。

    Returns:
        成功：{
            duration_minutes, distance_km, transit_fee, taxi_fee,
            steps: [{instruction, mode}],
            alternatives: [...]  # 备选方案（精简版）
        }
        失败：{error: str}
    """
    logger.info("tool_call", tool="transit_route",
                origin=origin, destination=destination,
                city1=city1, city2=city2, strategy=strategy)

    if not settings.AMAP_KEY or settings.AMAP_KEY.startswith("your_"):
        return _mock_transit(origin, destination, city1)

    # 兜底：如果调用方传了城市名而非 citycode，尝试自动转换
    city1_code = await _ensure_citycode(city1)
    city2_code = await _ensure_citycode(city2)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{AMAP_BASE}/v5/direction/transit/integrated",
                params={
                    "key": settings.AMAP_KEY,
                    "origin": origin,
                    "destination": destination,
                    "city1": city1_code,
                    "city2": city2_code,
                    "strategy": str(strategy),
                    "AlternativeRoute": str(alternative_route),
                    "nightflag": "0",
                    "show_fields": _TRANSIT_SHOW_FIELDS,
                },
            )
        data = r.json()
    except Exception as e:
        logger.error("transit_http_failed", error=str(e))
        return {"error": f"transit request failed: {e}"}

    # V5 错误判断：infocode != 10000 表示失败
    infocode = data.get("infocode")
    status = data.get("status")
    if status != "1" or (infocode and infocode != "10000"):
        info = data.get("info") or "unknown"
        logger.warning("transit_v5_failed",
                       infocode=infocode, info=info)
        return {"error": f"transit route failed (infocode={infocode}): {info}"}
    return data
    route = data.get("route", {}) or {}
    transits = route.get("transits") or []
    if not transits:
        return {"error": "no transit route found"}

    # 主方案
    main = transits[0]

    # 备选方案（精简）
    alternatives = []
    for t in transits[1:alternative_route]:
        alt = _parse_one_transit(t)
        alternatives.append({
            "duration_minutes": alt["duration_minutes"],
            "distance_km": alt["distance_km"],
            "transit_fee": alt["transit_fee"],
            "steps_count": len(alt["steps"]),
        })

    result = {
        **main,
    }
    logger.info("tool_done", tool="transit_route")
    return result


@tool
async def poi_search(keywords: str, types: str, region: str = "", city_limit: bool = False) -> dict:
    """通过关键字和 POI 类型搜索地点（V5 place/text 接口）。

    用于精确定位目的地/出发地的坐标。相比 geocode，poi_search 支持按 POI 类型过滤，
    可以避免把"东钱湖"这样的景点名解析到附近的住宅小区。

    Args:
        keywords: 地点关键字（如 "东钱湖"），只支持一个关键字，不超过80字符
        types: POI 类型编码（6位数字，如 "110200" 表示风景名胜），可传多个用 "|" 分隔
        region: 搜索区划（城市名/citycode/adcode），用于限制搜索结果范围
        city_limit: 是否严格限制在 region 对应区域内

    Returns:
        成功：{longitude, latitude, city, citycode, formatted, raw_name}
        失败：{error: str}
    """
    logger.info("tool_call", tool="poi_search", keywords=keywords, types=types, region=region)

    if not settings.AMAP_KEY or settings.AMAP_KEY.startswith("your_"):
        return _mock_poi_search(keywords, types, region)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{AMAP_BASE}/v5/place/text",
                params={
                    "key": settings.AMAP_KEY,
                    "keywords": keywords,
                    "types": types,
                    "region": region,
                    "city_limit": str(city_limit).lower(),
                    "page_size": "5",
                    "page_num": "1",
                },
            )
        data = r.json()
    except Exception as e:
        logger.error("poi_search_http_failed", error=str(e))
        return {"error": f"poi_search request failed: {e}"}

    infocode = data.get("infocode")
    status = data.get("status")
    if status != "1" or (infocode and infocode != "10000"):
        info = data.get("info") or "unknown"
        logger.warning("poi_search_v5_failed", infocode=infocode, info=info)
        return {"error": f"poi search failed (infocode={infocode}): {info}"}

    pois = data.get("pois") or []
    if not pois:
        logger.info("poi_search_empty", keywords=keywords, types=types)
        return {"error": f"no POI found for '{keywords}' (types={types})"}

    # 取第一个结果
    poi = pois[0]
    location = poi.get("location") or ""
    try:
        lng, lat = location.split(",")
    except ValueError:
        return {"error": f"unexpected poi location format: {location}"}

    result = {
        "longitude": float(lng),
        "latitude": float(lat),
        "city": poi.get("cityname") or poi.get("adname") or "",
        "citycode": poi.get("citycode") or "",
        "formatted": poi.get("address") or poi.get("name") or keywords,
        "raw_name": poi.get("name") or keywords,
    }
    logger.info("tool_done", tool="poi_search", result=result)
    return result


@tool
async def walking_route(origin: str, destination: str) -> dict:
    """步行路线规划（V5 walking 接口）。短距离接驳用。

    Args:
        origin: 起点经纬度字符串 "lng,lat"
        destination: 终点经纬度字符串 "lng,lat"

    Returns:
        成功：{duration_minutes, distance_km, steps: [str]}
        失败：{error: str}
    """
    logger.info("tool_call", tool="walking_route",
                origin=origin, destination=destination)
    if not settings.AMAP_KEY or settings.AMAP_KEY.startswith("your_"):
        return _mock_walking(origin, destination)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{AMAP_BASE}/v5/direction/walking",
                params={
                    "key": settings.AMAP_KEY,
                    "origin": origin,
                    "destination": destination,
                    "show_fields": "cost",
                },
            )
        data = r.json()
    except Exception as e:
        logger.error("walking_http_failed", error=str(e))
        return {"error": f"walking request failed: {e}"}

    infocode = data.get("infocode")
    if data.get("status") != "1" or (infocode and infocode != "10000"):
        info = data.get("info") or "unknown"
        logger.warning("walking_v5_failed", infocode=infocode, info=info)
        return {"error": f"walking route failed (infocode={infocode}): {info}"}

    paths = (data.get("route") or {}).get("paths") or []
    if not paths:
        return {"error": "no walking path found"}

    path = paths[0]
    cost = path.get("cost") or {}
    duration = int(cost.get("duration") or 0) // 60
    distance_km = round(int(path.get("distance") or 0) / 1000, 2)
    steps = []
    for s in (path.get("steps") or []):
        instr = s.get("instruction") or ""
        if instr:
            steps.append(instr)

    return {
        "duration_minutes": duration,
        "distance_km": distance_km,
        "steps": steps[:5],
    }


# ============================================================
# 内部辅助函数
# ============================================================

async def _ensure_citycode(city_or_code: str) -> str:
    """确保参数是 citycode。若传的是城市名，自动调 get_citycode 转换。"""
    if not city_or_code:
        return ""
    s = str(city_or_code).strip()
    if s.isdigit():
        return s
    # 是城市名 → 查 citycode
    return await get_citycode.ainvoke({"city_name": s})


def _normalize_city_key(city: str) -> str:
    """归一化城市名做缓存 key：去首尾空白 + 去 '市/区/县' 后缀。"""
    if not city:
        return ""
    c = city.strip()
    for suffix in ("市", "区", "县", "自治州", "地区"):
        if c.endswith(suffix):
            c = c[: -len(suffix)]
            break
    return c


def _parse_one_transit(transit: dict) -> dict:
    """解析 V5 transit 中的一个方案。

    V5 字段位置：
    - duration: transit.cost.duration（秒）
    - distance: transit.distance（米，直接在 transit 上）
    - transit_fee: 在 segments 下的某个 segment 中（V5 规范）
    - taxi_fee: transit.cost.taxi_fee（注意是 route 层级 cost，不是 transit 层级）

    实际上 V5 文档说 transit_fee 在 segments 下返回，taxi_fee 在 cost 下。
    但实测 transit.cost 也会同时返回 transit_fee 和 taxi_fee（兼容 V3 习惯）。
    我们两边都尝试取。
    """
    # cost 对象（V5 新增）
    cost = transit.get("cost") or {}
    duration_seconds = int(cost.get("duration") or 0)
    distance_meters = int(transit.get("distance") or 0)

    # transit_fee / taxi_fee
    transit_fee = cost.get("transit_fee") or ""
    taxi_fee = cost.get("taxi_fee") or ""

    # 如果 cost 里没有 transit_fee，尝试从 segments 里找
    if not transit_fee:
        for seg in (transit.get("segments") or []):
            seg_cost = (seg.get("bus") or {}).get("cost") or {}
            if seg_cost.get("transit_fee"):
                transit_fee = seg_cost["transit_fee"]
                break

    duration = duration_seconds // 60
    distance_km = round(distance_meters / 1000, 2)
    steps = _parse_transit_segments_v5(transit)

    return {
        "duration_minutes": duration,
        "distance_km": distance_km,
        "transit_fee": transit_fee,
        "taxi_fee": taxi_fee,
        "steps": steps[:5],
    }


def _parse_transit_segments_v5(transit: dict) -> list[dict]:
    """解析 V5 transit 的 segments 数组，提取人类可读的步骤。

    V5 segments 结构（参照文档）：
    [
      {
        "walking": {"distance": ..., "steps": [{"instruction": ...}]},
        "bus": {"buslines": [{"name": ..., "departure_stop": ..., "arrival_stop": ...}]},
        "railway": {"railways": [{"name": ..., "via_stops": ...}]}
      },
      ...
    ]
    """
    steps: list[dict] = []
    segments = transit.get("segments") or []

    for seg in segments:
        # 步行段
        walking = seg.get("walking") or {}
        if walking:
            w_steps = walking.get("steps") or []
            w_distance = walking.get("distance")
            if w_distance:
                w_distance_m = int(w_distance)
                if w_distance_m > 0:
                    sub_steps = [s.get("instruction", "") for s in w_steps if s.get("instruction")]
                    instr = "步行 " + str(w_distance_m) + "m"
                    if sub_steps:
                        instr += "（" + sub_steps[0] + "）"
                    steps.append({"instruction": instr, "mode": "walking"})
            elif w_steps:
                for s in w_steps:
                    instr = s.get("instruction") or ""
                    if instr:
                        steps.append({"instruction": "步行：" + instr, "mode": "walking"})

        # 公交段
        bus = seg.get("bus") or {}
        if bus:
            buslines = bus.get("buslines") or []
            for line in buslines:
                name = line.get("name") or ""
                dep = line.get("departure_stop") or {}
                arr = line.get("arrival_stop") or {}
                dep_name = dep.get("name") if isinstance(dep, dict) else str(dep)
                arr_name = arr.get("name") if isinstance(arr, dict) else str(arr)
                via_num = line.get("via_num") or ""
                instr_parts = []
                if name:
                    instr_parts.append(name)
                if dep_name and arr_name:
                    instr_parts.append(f"{dep_name} → {arr_name}")
                if via_num:
                    instr_parts.append(f"({via_num} 站)")
                if instr_parts:
                    steps.append({
                        "instruction": " ".join(instr_parts),
                        "mode": "bus",
                    })

        # 地铁/铁路段
        railway = seg.get("railway") or {}
        if railway:
            railways = railway.get("railways") or []
            for rw in railways:
                name = rw.get("name") or "地铁"
                dep = rw.get("departure_stop") or {}
                arr = rw.get("arrival_stop") or {}
                dep_name = dep.get("name") if isinstance(dep, dict) else str(dep)
                arr_name = arr.get("name") if isinstance(arr, dict) else str(arr)
                via_num = rw.get("via_num") or ""
                instr_parts = [name]
                if dep_name and arr_name:
                    instr_parts.append(f"{dep_name} → {arr_name}")
                if via_num:
                    instr_parts.append(f"({via_num} 站)")
                steps.append({
                    "instruction": " ".join(instr_parts),
                    "mode": "railway",
                })

    return steps


# ============================================================
# mock 数据（AMAP_KEY 未配置时用）
# ============================================================

_MOCK_LOCATIONS = {
    # 杭州
    "杭州电子科技大学研究生公寓": (120.194472, 30.298914, "杭州"),
    "杭州电子科技大学": (120.194472, 30.298914, "杭州"),
    "杭电": (120.194472, 30.298914, "杭州"),
    "杭州东站": (120.213333, 30.290556, "杭州"),
    "杭州东": (120.213333, 30.290556, "杭州"),
    "杭州站": (120.174444, 30.243056, "杭州"),
    "杭州西湖": (120.148732, 30.242885, "杭州"),
    "西湖": (120.148732, 30.242885, "杭州"),
    "杭州": (120.194472, 30.298914, "杭州"),
    # 宁波
    "宁波东钱湖": (121.622222, 29.766944, "宁波"),
    "东钱湖": (121.622222, 29.766944, "宁波"),
    "宁波站": (121.550556, 29.833611, "宁波"),
    "宁波": (121.550556, 29.833611, "宁波"),
    "宁波象山": (121.869251, 29.476826, "宁波"),
    "象山": (121.869251, 29.476826, "宁波"),
    # 上海
    "上海虹桥": (121.319722, 31.194167, "上海"),
    "上海": (121.457222, 31.251944, "上海"),
}

# mock citycode（仅用于 AMAP_KEY 未配置场景）
_MOCK_CITYCODE = {
    "杭州": "0571",
    "宁波": "0574",
    "上海": "021",
    "北京": "010",
    "南京": "025",
    "苏州": "0512",
    "绍兴": "0575",
    "嘉兴": "0573",
    "温州": "0577",
    "台州": "0576",
}


def _mock_geocode(address: str) -> dict:
    if address in _MOCK_LOCATIONS:
        lng, lat, city = _MOCK_LOCATIONS[address]
        return {"longitude": lng, "latitude": lat, "city": city, "formatted": address}
    for key, (lng, lat, city) in _MOCK_LOCATIONS.items():
        if key in address:
            return {"longitude": lng, "latitude": lat, "city": city, "formatted": address}
    return {
        "longitude": 120.194472,
        "latitude": 30.298914,
        "city": "杭州",
        "formatted": address,
    }


def _mock_reverse_geocode(lng: float, lat: float) -> str:
    if lat < 30.5 and lng > 121.0:
        return "宁波"
    if lat > 31.0 and lng > 121.0:
        return "上海"
    return "杭州"


def _mock_transit(origin: str, destination: str, city_code: str) -> dict:
    return {
        "duration_minutes": 30,
        "distance_km": 12.5,
        "transit_fee": "4",
        "taxi_fee": "35",
        "steps": [
            {"instruction": "步行 350m 至最近地铁站", "mode": "walking"},
            {"instruction": "地铁 1 号线 (5 站)", "mode": "railway"},
            {"instruction": "步行 200m 至目的地", "mode": "walking"},
        ],
        "alternatives": [],
    }


def _mock_poi_search(keywords: str, types: str, region: str) -> dict:
    """Mock POI search for when AMAP_KEY is not configured."""
    # 如果用户输入包含已知地点，返回景点坐标
    for key, (lng, lat, city) in _MOCK_LOCATIONS.items():
        if key in keywords or keywords in key:
            return {
                "longitude": lng,
                "latitude": lat,
                "city": city,
                "citycode": _MOCK_CITYCODE.get(city, ""),
                "formatted": key,
                "raw_name": key,
            }
    return {
        "longitude": 121.622222,
        "latitude": 29.766944,
        "city": "宁波",
        "citycode": "0574",
        "formatted": keywords,
        "raw_name": keywords,
    }


def _mock_walking(origin: str, destination: str) -> dict:
    return {
        "duration_minutes": 8,
        "distance_km": 0.6,
        "steps": ["步行约 600 米"],
    }
