from flask import Blueprint, request, jsonify
from models import db, Route, RouteStop, Order, Warehouse, Stock

bp = Blueprint("routes_api", __name__)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _build_stock_map(warehouse_ids: list[int]) -> dict:
    """Returns {warehouse_id: {product_id: available_qty}}."""
    stocks = Stock.query.filter(Stock.warehouse_id.in_(warehouse_ids)).all()
    result: dict = {}
    for s in stocks:
        result.setdefault(s.warehouse_id, {})[s.product_id] = s.quantity
    return result


def _aggregate_stock_checks(orders, warehouses):
    """Aggregated check across all warehouses for the given orders."""
    from collections import defaultdict
    required: dict = defaultdict(float)
    meta: dict = {}
    for o in orders:
        required[o.product_id] += o.quantity
        if o.product_id not in meta:
            meta[o.product_id] = {
                "name": o.product.name if o.product else f"ID {o.product_id}",
                "unit": o.product.unit if o.product else "",
            }
    checks = []
    stock_map = _build_stock_map([w.id for w in warehouses])
    for pid, total_req in required.items():
        total_avail = sum(stock_map.get(w.id, {}).get(pid, 0) for w in warehouses)
        checks.append({
            "product_name": meta[pid]["name"],
            "unit":         meta[pid]["unit"],
            "required":     total_req,
            "available":    total_avail,
            "ok":           total_avail >= total_req,
            "by_warehouse": [
                {"warehouse_name": w.name,
                 "available": stock_map.get(w.id, {}).get(pid, 0)}
                for w in warehouses
            ],
        })
    return checks


# ─────────────────────────────────────────────────────────────────────
# Single-warehouse optimize (backward compat)
# ─────────────────────────────────────────────────────────────────────

@bp.route("/api/optimize_route", methods=["POST"])
def optimize():
    from services.route_optimizer import optimize_route
    from collections import defaultdict

    data         = request.get_json(silent=True) or {}
    order_ids    = data.get("order_ids", [])
    warehouse_id = data.get("warehouse_id")

    if not order_ids:
        return jsonify({"error": "Укажите хотя бы один заказ"}), 400
    if not warehouse_id:
        return jsonify({"error": "Укажите стартовый склад"}), 400

    warehouse = db.get_or_404(Warehouse, warehouse_id)
    orders    = Order.query.filter(Order.id.in_(order_ids)).all()
    if not orders:
        return jsonify({"error": "Заказы не найдены"}), 404

    stock_map     = _build_stock_map([warehouse.id])
    stock_checks  = _aggregate_stock_checks(orders, [warehouse])

    orders_list = [{"id": o.id, "lat": o.delivery_lat, "lon": o.delivery_lon,
                    "address": o.delivery_address,
                    "product_name": o.product.name if o.product else "",
                    "quantity": o.quantity} for o in orders]

    result = optimize_route(orders_list, warehouse.to_dict())
    result["stock_checks"]  = stock_checks
    result["warehouse_id"]  = warehouse_id
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────
# Multi-warehouse optimize (new)
# ─────────────────────────────────────────────────────────────────────

@bp.route("/api/optimize_routes", methods=["POST"])
def optimize_multi():
    from services.route_optimizer import optimize_multi_warehouse

    data          = request.get_json(silent=True) or {}
    order_ids     = data.get("order_ids", [])
    warehouse_ids = data.get("warehouse_ids", [])

    if not order_ids:
        return jsonify({"error": "Укажите хотя бы один заказ"}), 400
    if not warehouse_ids:
        return jsonify({"error": "Укажите хотя бы один склад"}), 400

    warehouses = Warehouse.query.filter(Warehouse.id.in_(warehouse_ids)).all()
    orders     = Order.query.filter(Order.id.in_(order_ids)).all()

    if not warehouses:
        return jsonify({"error": "Склады не найдены"}), 404
    if not orders:
        return jsonify({"error": "Заказы не найдены"}), 404

    stock_map = _build_stock_map([w.id for w in warehouses])

    orders_list = [{
        "id":           o.id,
        "product_id":   o.product_id,
        "quantity":     o.quantity,
        "lat":          o.delivery_lat,
        "lon":          o.delivery_lon,
        "address":      o.delivery_address,
        "product_name": o.product.name if o.product else "",
        "unit":         o.product.unit if o.product else "",
    } for o in orders]

    wh_list = [w.to_dict() for w in warehouses]

    result = optimize_multi_warehouse(orders_list, wh_list, stock_map)
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────
# CRUD — list / get / delete
# ─────────────────────────────────────────────────────────────────────

@bp.route("/api/routes", methods=["GET"])
def list_routes():
    status = request.args.get("status")
    q = Route.query.order_by(Route.created_at.desc())
    if status:
        q = q.filter_by(status=status)
    return jsonify([r.to_dict() for r in q.all()])


@bp.route("/api/routes/<int:rid>", methods=["GET"])
def get_route(rid):
    return jsonify(db.get_or_404(Route, rid).to_dict())


@bp.route("/api/routes/<int:rid>", methods=["DELETE"])
def delete_route(rid):
    r = db.get_or_404(Route, rid)
    db.session.delete(r)
    db.session.commit()
    return jsonify({"message": "Маршрут удалён"})


# ─────────────────────────────────────────────────────────────────────
# Create single route (backward compat)
# ─────────────────────────────────────────────────────────────────────

@bp.route("/api/routes", methods=["POST"])
def create_route():
    data    = request.get_json(silent=True) or {}
    missing = [f for f in ["name", "stops", "total_distance"] if data.get(f) is None]
    if missing:
        return jsonify({"error": f"Обязательные поля: {', '.join(missing)}"}), 400

    warehouse_id       = data.get("warehouse_id")
    order_ids_in_route = [s["order_id"] for s in data["stops"] if s.get("order_id")]
    orders             = Order.query.filter(Order.id.in_(order_ids_in_route)).all()

    if warehouse_id:
        from collections import defaultdict
        req: dict = defaultdict(float)
        meta: dict = {}
        for o in orders:
            req[o.product_id] += o.quantity
            meta[o.product_id] = {
                "name": o.product.name if o.product else f"ID {o.product_id}",
                "unit": o.product.unit if o.product else "",
            }
        insufficient = []
        for pid, total_req in req.items():
            stock = Stock.query.filter_by(warehouse_id=warehouse_id, product_id=pid).first()
            avail = stock.quantity if stock else 0
            if avail < total_req:
                insufficient.append(
                    f"«{meta[pid]['name']}»: требуется {total_req} {meta[pid]['unit']}, "
                    f"доступно {avail} {meta[pid]['unit']}"
                )
        if insufficient:
            return jsonify({"error": "Недостаточно товаров на складе",
                            "details": insufficient}), 409

    route = Route(name=data["name"], confirmed=True,
                  total_distance=float(data.get("total_distance", 0)),
                  status="pending")
    db.session.add(route)
    db.session.flush()

    for s in data["stops"]:
        db.session.add(RouteStop(
            route_id=route.id, stop_order=s["stop_order"],
            order_id=s.get("order_id"), warehouse_id=s.get("warehouse_id"),
            lat=float(s["lat"]), lon=float(s["lon"]),
            address=s["address"], stop_type=s.get("type", "delivery"),
        ))

    if order_ids_in_route:
        Order.query.filter(Order.id.in_(order_ids_in_route)).update(
            {"status": "in_route"}, synchronize_session=False)

    if warehouse_id:
        for o in orders:
            stock = Stock.query.filter_by(warehouse_id=warehouse_id,
                                          product_id=o.product_id).first()
            if stock:
                stock.quantity = max(0, stock.quantity - o.quantity)

    db.session.commit()
    return jsonify(route.to_dict()), 201


# ─────────────────────────────────────────────────────────────────────
# Create multiple routes in one transaction (multi-warehouse)
# ─────────────────────────────────────────────────────────────────────

@bp.route("/api/routes/batch", methods=["POST"])
def create_routes_batch():
    """
    Сохраняет несколько маршрутов за одну транзакцию.

    Body:
    {
        "routes": [
            {
                "name": str,
                "total_distance": float,
                "home_warehouse_id": int,
                "stops": [...],        # stop.source_warehouse_id present on delivery stops
                "order_ids": [...]
            }
        ],
        "assignment": { "order_id": warehouse_id }  # для списания
    }
    """
    data = request.get_json(silent=True) or {}
    routes_data = data.get("routes", [])

    if not routes_data:
        return jsonify({"error": "Нет маршрутов для сохранения"}), 400

    # assignment format from optimizer: {str(order_id): [[wh_id, qty], ...]}
    assignment_norm: dict[int, list] = {
        int(k): v for k, v in data.get("assignment", {}).items()
    }

    # Collect all orders for pre-check
    all_order_ids = []
    for rd in routes_data:
        all_order_ids.extend(rd.get("order_ids", []))
    all_orders = Order.query.filter(Order.id.in_(all_order_ids)).all()
    orders_map = {o.id: o for o in all_orders}

    # ── Stock check per (source_warehouse, product) ───────────────────
    from collections import defaultdict
    needed: dict = defaultdict(lambda: defaultdict(float))  # wh_id -> {pid -> qty}
    for o in all_orders:
        sources = assignment_norm.get(o.id, [])
        for (wh_id, qty) in sources:
            needed[wh_id][o.product_id] += qty

    insufficient = []
    for wh_id, products in needed.items():
        wh_obj = db.session.get(Warehouse, wh_id)
        for pid, total_req in products.items():
            stock = Stock.query.filter_by(warehouse_id=wh_id, product_id=pid).first()
            avail = stock.quantity if stock else 0
            if avail < total_req:
                # find a product name from orders
                prod_name = next(
                    (o.product.name for o in all_orders
                     if o.product_id == pid and o.product), str(pid)
                )
                insufficient.append(
                    f"Склад «{wh_obj.name if wh_obj else wh_id}», "
                    f"«{prod_name}»: требуется {total_req}, доступно {avail}"
                )
    if insufficient:
        return jsonify({"error": "Недостаточно товаров",
                        "details": insufficient}), 409

    # ── Save routes ──────────────────────────────────────────────────
    saved_routes = []
    for rd in routes_data:
        route = Route(
            name=rd.get("name", "Маршрут"),
            confirmed=True,
            total_distance=float(rd.get("total_distance", 0)),
            status="pending",
        )
        db.session.add(route)
        db.session.flush()

        for s in rd.get("stops", []):
            stop_type = s.get("type", "delivery")
            # warehouse_return is still a warehouse stop for DB purposes
            db_type = "warehouse" if stop_type in ("warehouse", "warehouse_return") else "delivery"
            db.session.add(RouteStop(
                route_id=route.id,
                stop_order=s["stop_order"],
                order_id=s.get("order_id"),
                warehouse_id=s.get("warehouse_id"),
                lat=float(s["lat"]),
                lon=float(s["lon"]),
                address=s["address"],
                stop_type=db_type,
            ))

        order_ids = rd.get("order_ids", [])
        if order_ids:
            Order.query.filter(Order.id.in_(order_ids)).update(
                {"status": "in_route"}, synchronize_session=False)

        saved_routes.append(route)

    # ── Deduct stock per source warehouse (split-aware) ──────────────
    for o in all_orders:
        sources = assignment_norm.get(o.id, [])
        for (wh_id, qty) in sources:
            stock = Stock.query.filter_by(warehouse_id=wh_id,
                                          product_id=o.product_id).first()
            if stock:
                stock.quantity = max(0, stock.quantity - qty)

    db.session.commit()
    return jsonify([r.to_dict() for r in saved_routes]), 201


# ─────────────────────────────────────────────────────────────────────
# Driver actions
# ─────────────────────────────────────────────────────────────────────

@bp.route("/api/routes/<int:rid>/start", methods=["PATCH"])
def start_route(rid):
    r = db.get_or_404(Route, rid)
    if r.status != "pending":
        return jsonify({"error": "Маршрут уже начат или завершён"}), 400
    r.status = "in_progress"
    db.session.commit()
    return jsonify(r.to_dict())


@bp.route("/api/routes/<int:rid>/stops/<int:stop_id>/result", methods=["PATCH"])
def set_stop_result(rid, stop_id):
    r    = db.get_or_404(Route, rid)
    stop = db.get_or_404(RouteStop, stop_id)

    if stop.route_id != rid:
        return jsonify({"error": "Остановка не принадлежит этому маршруту"}), 400
    if r.status != "in_progress":
        return jsonify({"error": "Маршрут не активен"}), 400
    if stop.stop_type != "delivery":
        return jsonify({"error": "Эта остановка не является доставкой"}), 400

    data   = request.get_json(silent=True) or {}
    result = data.get("result")
    if result not in ("success", "failure"):
        return jsonify({"error": "result должен быть 'success' или 'failure'"}), 400

    stop.delivery_result = result
    if stop.order_id:
        order = db.session.get(Order, stop.order_id)
        if order:
            order.status = "completed" if result == "success" else "failed"

    delivery_stops = [s for s in r.stops if s.stop_type == "delivery"]
    all_marked     = all(s.delivery_result is not None for s in delivery_stops)
    if all_marked and delivery_stops:
        r.status = ("completed"
                    if all(s.delivery_result == "success" for s in delivery_stops)
                    else "requires_intervention")

    db.session.commit()
    return jsonify(r.to_dict())
