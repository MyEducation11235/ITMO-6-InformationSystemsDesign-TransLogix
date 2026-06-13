from flask import Blueprint, request, jsonify
from models import db, Order, Product

bp = Blueprint("orders", __name__)


@bp.route("/api/orders", methods=["GET"])
def list_orders():
    status = request.args.get("status")
    q = Order.query.order_by(Order.created_at.desc())
    if status:
        q = q.filter_by(status=status)
    return jsonify([o.to_dict() for o in q.all()])


@bp.route("/api/orders/<int:oid>", methods=["GET"])
def get_order(oid):
    o = db.get_or_404(Order, oid)
    return jsonify(o.to_dict())


@bp.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json(silent=True) or {}
    required = ["product_id", "quantity", "delivery_address", "delivery_lat", "delivery_lon"]
    missing = [f for f in required if data.get(f) is None and data.get(f) != 0]
    if missing:
        return jsonify({"error": f"Обязательные поля: {', '.join(missing)}"}), 400

    product = db.get_or_404(Product, data["product_id"])

    order = Order(
        product_id=product.id,
        quantity=float(data["quantity"]),
        delivery_address=data["delivery_address"],
        delivery_lat=float(data["delivery_lat"]),
        delivery_lon=float(data["delivery_lon"]),
        status="new",
    )
    db.session.add(order)
    db.session.commit()
    return jsonify(order.to_dict()), 201


@bp.route("/api/orders/<int:oid>", methods=["PUT"])
def update_order(oid):
    order = db.get_or_404(Order, oid)
    data = request.get_json(silent=True) or {}
    if "status" in data:
        if data["status"] not in ("new", "in_route", "completed"):
            return jsonify({"error": "Недопустимый статус"}), 400
        order.status = data["status"]
    if "quantity" in data:
        order.quantity = float(data["quantity"])
    if "delivery_address" in data:
        order.delivery_address = data["delivery_address"]
    if "delivery_lat" in data:
        order.delivery_lat = float(data["delivery_lat"])
    if "delivery_lon" in data:
        order.delivery_lon = float(data["delivery_lon"])
    db.session.commit()
    return jsonify(order.to_dict())


@bp.route("/api/orders/<int:oid>", methods=["DELETE"])
def delete_order(oid):
    order = db.get_or_404(Order, oid)
    db.session.delete(order)
    db.session.commit()
    return jsonify({"message": "Заказ удалён"})
