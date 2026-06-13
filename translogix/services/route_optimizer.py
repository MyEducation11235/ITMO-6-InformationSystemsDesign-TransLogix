"""
Сервис оптимизации маршрутов.
Реализует алгоритм «ближайший сосед» (Nearest Neighbour) для задачи коммивояжёра (TSP).
"""

import math


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Вычисляет расстояние между двумя точками на Земле в километрах
    по формуле Гаверсинуса.
    """
    R = 6371.0  # радиус Земли в километрах
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def nearest_neighbour_tsp(points: list[dict]) -> tuple[list[dict], float]:
    """
    Алгоритм «ближайший сосед» для TSP.

    Параметры:
        points: список точек, каждая содержит {'lat', 'lon', ...}.
                Первый элемент — стартовая точка (склад), она остаётся на месте.

    Возвращает:
        (ordered_points, total_distance_km)
    """
    if not points:
        return [], 0.0

    if len(points) == 1:
        return points, 0.0

    # Стартовая точка фиксирована (склад)
    start = points[0]
    unvisited = list(points[1:])
    route = [start]
    total_distance = 0.0
    current = start

    while unvisited:
        # Найти ближайшую непосещённую точку
        best_dist = float("inf")
        best_idx = 0
        for i, pt in enumerate(unvisited):
            dist = haversine_distance(current["lat"], current["lon"], pt["lat"], pt["lon"])
            if dist < best_dist:
                best_dist = dist
                best_idx = i

        nearest = unvisited.pop(best_idx)
        total_distance += best_dist
        route.append(nearest)
        current = nearest

    return route, round(total_distance, 2)


def optimize_route(orders: list[dict], warehouse: dict) -> dict:
    """
    Строит оптимальный маршрут доставки.

    Параметры:
        orders:    список заказов [{'id', 'lat', 'lon', 'address', ...}]
        warehouse: стартовый склад {'id', 'lat', 'lon', 'address', 'name'}

    Возвращает:
        {
            'stops': [{'type': 'warehouse'|'delivery', 'id': ..., 'lat', 'lon', 'address', 'order_id', 'warehouse_id'}],
            'total_distance': km (float)
        }
    """
    if not orders:
        return {"stops": [], "total_distance": 0.0}

    # Собираем точки: склад первый, затем заказы
    points = [
        {
            "type": "warehouse",
            "id": warehouse["id"],
            "lat": warehouse["lat"],
            "lon": warehouse["lon"],
            "address": warehouse["address"],
            "name": warehouse["name"],
            "order_id": None,
            "warehouse_id": warehouse["id"],
        }
    ]

    for order in orders:
        points.append(
            {
                "type": "delivery",
                "id": order["id"],
                "lat": order["lat"],
                "lon": order["lon"],
                "address": order["address"],
                "order_id": order["id"],
                "warehouse_id": None,
            }
        )

    ordered_points, total_distance = nearest_neighbour_tsp(points)

    # Формируем остановки с порядковыми номерами
    stops = []
    for idx, pt in enumerate(ordered_points):
        stops.append(
            {
                "stop_order": idx,
                "type": pt["type"],
                "id": pt["id"],
                "lat": pt["lat"],
                "lon": pt["lon"],
                "address": pt["address"],
                "order_id": pt.get("order_id"),
                "warehouse_id": pt.get("warehouse_id"),
                "name": pt.get("name"),
            }
        )

    return {"stops": stops, "total_distance": total_distance}
