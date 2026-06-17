from flask import Blueprint, request, jsonify
from models import db, Route, RouteStop, Order, Warehouse, Stock

bp = Blueprint("routes_api", __name__)


# ─────────────────────────────────────────────
# Optimize (preview, no save)
# ─────────────────────────────────────────────
@bp.route("/api/optimize_route", methods=["POST"])
def optimize():
    from services.route_optimizer import optimize_route

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

    # Stock availability check
    stock_checks = []
    for o in orders:
        stock     = Stock.query.filter_by(warehouse_id=warehouse.id, product_id=o.product_id).first()
        available = stock.quantity if stock else 0
        stock_checks.append({
            "order_id":    o.id,
            "product_name": o.product.name if o.product else "",
            "unit":        o.product.unit  if o.product else "",
            "required":    o.quantity,
            "available":   available,
            "ok":          available >= o.quantity,
        })

    wh_dict = {"id": warehouse.id, "lat": warehouse.lat, "lon": warehouse.lon,
               "address": warehouse.address, "name": warehouse.name}
    orders_list = [{"id": o.id, "lat": o.delivery_lat, "lon": o.delivery_lon,
                    "address": o.delivery_address,
                    "product_name": o.product.name if o.product else "",
                    "quantity": o.quantity} for o in orders]

    result = optimize_route(orders_list, wh_dict)
    result["stock_checks"]  = stock_checks
    result["warehouse_id"]  = warehouse_id
    return jsonify(result)


# ─────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────
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


@bp.route("/api/routes", methods=["POST"])
def create_route():
    data = request.get_json(silent=True) or {}
    missing = [f for f in ["name", "stops", "total_distance"] if data.get(f) is None]
    if missing:
        return jsonify({"error": f"Обязательные поля: {', '.join(missing)}"}), 400

    warehouse_id = data.get("warehouse_id")
    order_ids_in_route = [s["order_id"] for s in data["stops"] if s.get("order_id")]
    orders = Order.query.filter(Order.id.in_(order_ids_in_route)).all()

    # Stock check
    if warehouse_id:
        insufficient = []
        for o in orders:
            stock     = Stock.query.filter_by(warehouse_id=warehouse_id, product_id=o.product_id).first()
            available = stock.quantity if stock else 0
            if available < o.quantity:
                pname = o.product.name if o.product else f"ID {o.product_id}"
                unit  = o.product.unit  if o.product else ""
                insufficient.append(f"«{pname}»: требуется {o.quantity} {unit}, доступно {available} {unit}")
        if insufficient:
            return jsonify({"error": "Недостаточно товаров на складе", "details": insufficient}), 409

    route = Route(
        name=data["name"], confirmed=True,
        total_distance=float(data.get("total_distance", 0)),
        status="pending",
    )
    db.session.add(route)
    db.session.flush()

    for stop_data in data["stops"]:
        db.session.add(RouteStop(
            route_id=route.id, stop_order=stop_data["stop_order"],
            order_id=stop_data.get("order_id"), warehouse_id=stop_data.get("warehouse_id"),
            lat=float(stop_data["lat"]), lon=float(stop_data["lon"]),
            address=stop_data["address"], stop_type=stop_data.get("type", "delivery"),
        ))

    if order_ids_in_route:
        Order.query.filter(Order.id.in_(order_ids_in_route)).update(
            {"status": "in_route"}, synchronize_session=False
        )

    if warehouse_id:
        for o in orders:
            stock = Stock.query.filter_by(warehouse_id=warehouse_id, product_id=o.product_id).first()
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


# ─────────────────────────────────────────────
# Driver actions
# ─────────────────────────────────────────────
@bp.route("/api/routes/<int:rid>/start", methods=["PATCH"])
def start_route(rid):
    """Водитель начинает маршрут → pending → in_progress."""
    r = db.get_or_404(Route, rid)
    if r.status != "pending":
        return jsonify({"error": "Маршрут уже начат или завершён"}), 400
    r.status = "in_progress"
    db.session.commit()
    return jsonify(r.to_dict())


@bp.route("/api/routes/<int:rid>/stops/<int:stop_id>/result", methods=["PATCH"])
def set_stop_result(rid, stop_id):
    """
    Водитель отмечает результат доставки по остановке.
    body: { "result": "success" | "failure" }
    После отметки автоматически пересчитывается статус маршрута.
    """
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

    # Update linked order status
    if stop.order_id:
        order = db.session.get(Order, stop.order_id)
        if order:
            order.status = "completed" if result == "success" else "failed"

    # Recalculate route status based on all delivery stops
    delivery_stops = [s for s in r.stops if s.stop_type == "delivery"]
    all_marked     = all(s.delivery_result is not None for s in delivery_stops)

    if all_marked and delivery_stops:
        if all(s.delivery_result == "success" for s in delivery_stops):
            r.status = "completed"
        else:
            r.status = "requires_intervention"

    db.session.commit()
    return jsonify(r.to_dict())
