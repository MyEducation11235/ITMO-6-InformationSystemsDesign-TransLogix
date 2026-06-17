"""
Сервис оптимизации маршрутов.

Функции:
  - haversine_distance      — расстояние между двумя точками (км)
  - nearest_neighbour_tsp   — алгоритм «ближайший сосед» для TSP
  - optimize_route          — однодепотный маршрут (обратная совместимость)
  - optimize_multi_warehouse — многоскладовой VRP с ограничением «погрузка до доставки»
"""

import math
from collections import defaultdict


# ─────────────────────────────────────────────────────────────────────
# Базовые геофункции
# ─────────────────────────────────────────────────────────────────────

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_neighbour_tsp(points: list[dict]) -> tuple[list[dict], float]:
    if not points:
        return [], 0.0
    if len(points) == 1:
        return points, 0.0

    start = points[0]
    unvisited = list(points[1:])
    route = [start]
    total = 0.0
    current = start

    while unvisited:
        best_d, best_i = float("inf"), 0
        for i, pt in enumerate(unvisited):
            d = haversine_distance(current["lat"], current["lon"], pt["lat"], pt["lon"])
            if d < best_d:
                best_d, best_i = d, i
        nearest = unvisited.pop(best_i)
        total += best_d
        route.append(nearest)
        current = nearest

    return route, round(total, 2)


# ─────────────────────────────────────────────────────────────────────
# Однодепотный маршрут (обратная совместимость)
# ─────────────────────────────────────────────────────────────────────

def optimize_route(orders: list[dict], warehouse: dict) -> dict:
    if not orders:
        return {"stops": [], "total_distance": 0.0}

    points = [{
        "type": "warehouse", "id": warehouse["id"],
        "lat": warehouse["lat"], "lon": warehouse["lon"],
        "address": warehouse["address"], "name": warehouse["name"],
        "order_id": None, "warehouse_id": warehouse["id"],
    }]
    for o in orders:
        points.append({
            "type": "delivery", "id": o["id"],
            "lat": o["lat"], "lon": o["lon"],
            "address": o["address"], "order_id": o["id"],
            "warehouse_id": None,
        })

    ordered, dist = nearest_neighbour_tsp(points)
    stops = [{"stop_order": i, "type": p["type"], "id": p["id"],
              "lat": p["lat"], "lon": p["lon"], "address": p["address"],
              "order_id": p.get("order_id"), "warehouse_id": p.get("warehouse_id"),
              "name": p.get("name")} for i, p in enumerate(ordered)]
    return {"stops": stops, "total_distance": dist}


# ─────────────────────────────────────────────────────────────────────
# Многоскладовой VRP с ограничением «погрузка → доставка»
# ─────────────────────────────────────────────────────────────────────

def _dist(a: dict, b: dict) -> float:
    return haversine_distance(a["lat"], a["lon"], b["lat"], b["lon"])


def _plan_route_with_constraints(
    home_wh: dict,
    orders_for_route: list[dict],
    wh_lookup: dict,
    assignment: dict,   # order_id -> [(warehouse_id, quantity), ...]
) -> tuple[list[dict], float]:
    """
    Строит один маршрут, начинающийся и заканчивающийся в home_wh.
    Ограничение: заказ можно доставить только после погрузки на ВСЕХ складах,
    которые участвуют в его выполнении (в т.ч. при разбивке).

    Возвращает (stops_list, total_distance).
    """
    if not orders_for_route:
        return [], 0.0

    # Все склады, которые нужно посетить для погрузки (помимо home)
    pickup_needed: set[int] = set()
    for o in orders_for_route:
        for (wh_id, _qty) in assignment[o["id"]]:
            if wh_id != home_wh["id"]:
                pickup_needed.add(wh_id)

    loaded_wh: set[int] = {home_wh["id"]}
    remaining_pickups = set(pickup_needed)
    remaining_deliveries = list(orders_for_route)

    def delivery_ready(o: dict) -> bool:
        """True когда ВСЕ склады-источники этого заказа уже загружены."""
        return all(wh_id in loaded_wh for (wh_id, _) in assignment[o["id"]])

    stops: list[dict] = []
    current = home_wh
    total_dist = 0.0

    stops.append({
        "type": "warehouse", "warehouse_id": home_wh["id"],
        "lat": home_wh["lat"], "lon": home_wh["lon"],
        "address": home_wh["address"], "name": home_wh["name"],
        "order_id": None, "is_home": True,
    })

    while remaining_pickups or remaining_deliveries:
        best_d = float("inf")
        best_obj = None
        best_kind = None

        # Варианты: склады для погрузки (всегда допустимы)
        for wh_id in remaining_pickups:
            wh = wh_lookup[wh_id]
            d = _dist(current, wh)
            if d < best_d:
                best_d, best_obj, best_kind = d, wh, "pickup"

        # Варианты: доставки (допустимы когда все источники уже загружены)
        for o in remaining_deliveries:
            if delivery_ready(o):
                d = _dist(current, o)
                if d < best_d:
                    best_d, best_obj, best_kind = d, o, "delivery"

        # Тупик — принудительно идём к ближайшему ещё непосещённому складу
        if best_obj is None:
            if remaining_pickups:
                wh_id = min(remaining_pickups,
                            key=lambda wid: _dist(current, wh_lookup[wid]))
                best_obj = wh_lookup[wh_id]
                best_d   = _dist(current, best_obj)
                best_kind = "pickup"
            else:
                break

        total_dist += best_d
        current = best_obj

        if best_kind == "pickup":
            remaining_pickups.discard(best_obj["id"])
            loaded_wh.add(best_obj["id"])
            stops.append({
                "type": "warehouse", "warehouse_id": best_obj["id"],
                "lat": best_obj["lat"], "lon": best_obj["lon"],
                "address": best_obj["address"], "name": best_obj["name"],
                "order_id": None, "is_home": False,
            })
        else:
            remaining_deliveries.remove(best_obj)
            stops.append({
                "type": "delivery", "warehouse_id": None,
                "lat": best_obj["lat"], "lon": best_obj["lon"],
                "address": best_obj["address"], "name": None,
                "order_id": best_obj["id"],
            })

    # Возврат на домашний склад
    total_dist += _dist(current, home_wh)
    stops.append({
        "type": "warehouse_return", "warehouse_id": home_wh["id"],
        "lat": home_wh["lat"], "lon": home_wh["lon"],
        "address": home_wh["address"], "name": home_wh["name"],
        "order_id": None, "is_home": True,
    })

    for i, s in enumerate(stops):
        s["stop_order"] = i

    return stops, round(total_dist, 2)


def _assign_orders_split(
    orders: list[dict],
    warehouses: list[dict],
    stock_map: dict,   # warehouse_id -> {product_id -> qty}
) -> dict:
    """
    Назначает каждый заказ на склады с учётом разбивки:
    один заказ может быть частично выполнен с нескольких складов.

    Возвращает {order_id: [(warehouse_id, quantity), ...]}
    """
    remaining = {
        w["id"]: defaultdict(float, stock_map.get(w["id"], {}))
        for w in warehouses
    }
    assignment: dict[int, list] = {}

    for o in orders:
        needed = float(o["quantity"])
        sources: list[tuple] = []

        # Сначала пробуем покрыть одним складом (минимизируем разбивку)
        single = [
            w for w in warehouses
            if remaining[w["id"]][o["product_id"]] >= needed
        ]
        if single:
            best = min(single, key=lambda w: _dist(o, w))
            sources.append((best["id"], needed))
            remaining[best["id"]][o["product_id"]] -= needed
        else:
            # Разбиваем по нескольким складам (от ближайшего к дальнему)
            sorted_wh = sorted(
                warehouses,
                key=lambda w: _dist(o, w)
            )
            for wh in sorted_wh:
                avail = remaining[wh["id"]].get(o["product_id"], 0)
                if avail > 0 and needed > 0:
                    take = min(avail, needed)
                    sources.append((wh["id"], take))
                    remaining[wh["id"]][o["product_id"]] -= take
                    needed -= take
                if needed <= 0:
                    break

            if needed > 1e-9:
                raise ValueError(
                    f"Заказ #{o['id']}: суммарно на складах недостаточно "
                    f"товара «{o.get('product_name', '')}»"
                )

        assignment[o["id"]] = sources

    return assignment


def optimize_multi_warehouse(
    orders: list[dict],
    warehouses: list[dict],
    stock_map: dict,
) -> dict:
    """
    Главная функция многоскладового VRP.

    Параметры:
        orders:     [{id, product_id, quantity, lat, lon, address, product_name}]
        warehouses: [{id, lat, lon, address, name}]  — выбранные склады
        stock_map:  {warehouse_id: {product_id: available_qty}}

    Возвращает:
        {
            routes: [
                {
                    home_warehouse_id: int,
                    home_warehouse_name: str,
                    stops: [...],
                    total_distance: float,
                    order_ids: [...]
                }
            ],
            total_distance: float,
            assignment: {order_id: warehouse_id},
            stock_checks: [...]
        }
    """
    if not orders or not warehouses:
        return {"routes": [], "total_distance": 0.0,
                "assignment": {}, "stock_checks": []}

    wh_lookup = {w["id"]: w for w in warehouses}

    # ── 1. Проверка суммарных остатков ────────────────────────────────
    required_by_product: dict[int, float] = defaultdict(float)
    product_meta: dict[int, dict] = {}
    for o in orders:
        required_by_product[o["product_id"]] += o["quantity"]
        if o["product_id"] not in product_meta:
            product_meta[o["product_id"]] = {
                "name": o.get("product_name", f"ID {o['product_id']}"),
                "unit": o.get("unit", ""),
            }

    stock_checks = []
    for pid, total_req in required_by_product.items():
        total_avail = sum(stock_map.get(w["id"], {}).get(pid, 0) for w in warehouses)
        wh_detail = [
            {"warehouse_name": wh_lookup[w["id"]]["name"],
             "available": stock_map.get(w["id"], {}).get(pid, 0)}
            for w in warehouses
        ]
        stock_checks.append({
            "product_name": product_meta[pid]["name"],
            "unit":         product_meta[pid]["unit"],
            "required":     total_req,
            "available":    total_avail,
            "ok":           total_avail >= total_req,
            "by_warehouse": wh_detail,
        })

    # ── 2. Назначение заказов на склады (с разбивкой) ─────────────────
    try:
        assignment = _assign_orders_split(orders, warehouses, stock_map)
        # assignment: {order_id: [(wh_id, qty), ...]}
    except ValueError as exc:
        return {"routes": [], "total_distance": 0.0,
                "assignment": {}, "stock_checks": stock_checks,
                "error": str(exc)}

    # ── 3. Перебор конфигураций маршрутов ────────────────────────────
    # Для группировки заказов по стартовым складам:
    # «основной» склад заказа = тот, что поставляет наибольшую долю
    def primary_wh(order_id: int) -> int:
        srcs = assignment[order_id]
        return max(srcs, key=lambda t: t[1])[0]

    orders_by_wh: dict[int, list] = defaultdict(list)
    for o in orders:
        orders_by_wh[primary_wh(o["id"])].append(o)

    active_whs = [w for w in warehouses if w["id"] in orders_by_wh]

    best_routes = None
    best_total  = float("inf")

    # Конфигурация A: отдельный маршрут от каждого «основного» склада
    config_a: list[dict] = []
    dist_a = 0.0
    for wh in active_whs:
        wh_orders = orders_by_wh[wh["id"]]
        stops, d = _plan_route_with_constraints(wh, wh_orders, wh_lookup, assignment)
        config_a.append({
            "home_warehouse_id":   wh["id"],
            "home_warehouse_name": wh["name"],
            "stops":               stops,
            "total_distance":      d,
            "order_ids":           [o["id"] for o in wh_orders],
        })
        dist_a += d

    if dist_a < best_total:
        best_total  = dist_a
        best_routes = config_a

    # Конфигурация B: единый маршрут от каждого склада (если складов > 1)
    if len(active_whs) > 1:
        for home_wh in warehouses:
            stops, d = _plan_route_with_constraints(
                home_wh, orders, wh_lookup, assignment
            )
            if d < best_total:
                best_total = d
                best_routes = [{
                    "home_warehouse_id":   home_wh["id"],
                    "home_warehouse_name": home_wh["name"],
                    "stops":               stops,
                    "total_distance":      d,
                    "order_ids":           [o["id"] for o in orders],
                }]

    # Сериализуем assignment в JSON-совместимый вид:
    # {str(order_id): [[wh_id, qty], ...]}
    assignment_json = {
        str(oid): [[wh_id, qty] for (wh_id, qty) in srcs]
        for oid, srcs in assignment.items()
    }

    return {
        "routes":         best_routes or [],
        "total_distance": round(best_total, 2),
        "assignment":     assignment_json,
        "stock_checks":   stock_checks,
    }
