from flask import Blueprint, request, jsonify
from models import db, Route, RouteStop, Order, Warehouse, Stock

bp = Blueprint("routes_api", __name__)


@bp.route("/api/optimize_route", methods=["POST"])
def optimize():
    """
    Принимает список order_id и warehouse_id стартового склада.
    Возвращает оптимальный маршрут (без сохранения в БД) + проверку остатков.
    """
    from services.route_optimizer import optimize_route

    data = request.get_json(silent=True) or {}
    order_ids = data.get("order_ids", [])
    warehouse_id = data.get("warehouse_id")

    if not order_ids:
        return jsonify({"error": "Укажите хотя бы один заказ"}), 400
    if not warehouse_id:
        return jsonify({"error": "Укажите стартовый склад"}), 400

    warehouse = db.get_or_404(Warehouse, warehouse_id)
    orders = Order.query.filter(Order.id.in_(order_ids)).all()

    if not orders:
        return jsonify({"error": "Заказы не найдены"}), 404

    # ── Stock availability check ──────────────────────────────────────
    stock_checks = []
    for o in orders:
        stock = Stock.query.filter_by(
            warehouse_id=warehouse.id,
            product_id=o.product_id
        ).first()
        available = stock.quantity if stock else 0
        stock_checks.append({
            "order_id": o.id,
            "product_name": o.product.name if o.product else "",
            "unit": o.product.unit if o.product else "",
            "required": o.quantity,
            "available": available,
            "ok": available >= o.quantity,
        })

    wh_dict = {
        "id": warehouse.id,
        "lat": warehouse.lat,
        "lon": warehouse.lon,
        "address": warehouse.address,
        "name": warehouse.name,
    }
    orders_list = [
        {
            "id": o.id,
            "lat": o.delivery_lat,
            "lon": o.delivery_lon,
            "address": o.delivery_address,
            "product_name": o.product.name if o.product else "",
            "quantity": o.quantity,
        }
        for o in orders
    ]

    result = optimize_route(orders_list, wh_dict)
    result["stock_checks"] = stock_checks
    result["warehouse_id"] = warehouse_id
    return jsonify(result)


@bp.route("/api/routes", methods=["GET"])
def list_routes():
    routes = Route.query.order_by(Route.created_at.desc()).all()
    return jsonify([r.to_dict() for r in routes])


@bp.route("/api/routes/<int:rid>", methods=["GET"])
def get_route(rid):
    r = db.get_or_404(Route, rid)
    return jsonify(r.to_dict())


@bp.route("/api/routes", methods=["POST"])
def create_route():
    """
    Сохраняет подтверждённый маршрут в БД, обновляет статусы заказов
    и списывает товары со склада.
    """
    data = request.get_json(silent=True) or {}
    required = ["name", "stops", "total_distance"]
    missing = [f for f in required if data.get(f) is None]
    if missing:
        return jsonify({"error": f"Обязательные поля: {', '.join(missing)}"}), 400

    warehouse_id = data.get("warehouse_id")

    # ── Stock check before saving ─────────────────────────────────────
    order_ids_in_route = [
        s["order_id"] for s in data["stops"] if s.get("order_id")
    ]
    orders = Order.query.filter(Order.id.in_(order_ids_in_route)).all()

    if warehouse_id:
        insufficient = []
        for o in orders:
            stock = Stock.query.filter_by(
                warehouse_id=warehouse_id,
                product_id=o.product_id
            ).first()
            available = stock.quantity if stock else 0
            if available < o.quantity:
                product_name = o.product.name if o.product else f"ID {o.product_id}"
                unit = o.product.unit if o.product else ""
                insufficient.append(
                    f"«{product_name}»: требуется {o.quantity} {unit}, "
                    f"доступно {available} {unit}"
                )
        if insufficient:
            return jsonify({
                "error": "Недостаточно товаров на складе",
                "details": insufficient,
            }), 409

    # ── Save route ────────────────────────────────────────────────────
    route = Route(
        name=data["name"],
        confirmed=True,
        total_distance=float(data.get("total_distance", 0)),
    )
    db.session.add(route)
    db.session.flush()

    for stop_data in data["stops"]:
        stop = RouteStop(
            route_id=route.id,
            stop_order=stop_data["stop_order"],
            order_id=stop_data.get("order_id"),
            warehouse_id=stop_data.get("warehouse_id"),
            lat=float(stop_data["lat"]),
            lon=float(stop_data["lon"]),
            address=stop_data["address"],
            stop_type=stop_data.get("type", "delivery"),
        )
        db.session.add(stop)

    # ── Update order statuses ─────────────────────────────────────────
    if order_ids_in_route:
        Order.query.filter(Order.id.in_(order_ids_in_route)).update(
            {"status": "in_route"}, synchronize_session=False
        )

    # ── Deduct stock from warehouse ───────────────────────────────────
    if warehouse_id:
        for o in orders:
            stock = Stock.query.filter_by(
                warehouse_id=warehouse_id,
                product_id=o.product_id
            ).first()
            if stock:
                stock.quantity = max(0, stock.quantity - o.quantity)

    db.session.commit()
    return jsonify(route.to_dict()), 201


@bp.route("/api/routes/<int:rid>", methods=["DELETE"])
def delete_route(rid):
    r = db.get_or_404(Route, rid)
    db.session.delete(r)
    db.session.commit()
    return jsonify({"message": "Маршрут удалён"})
