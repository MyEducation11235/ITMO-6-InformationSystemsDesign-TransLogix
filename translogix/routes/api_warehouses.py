from flask import Blueprint, request, jsonify
from models import db, Warehouse

bp = Blueprint("warehouses", __name__)


@bp.route("/api/warehouses", methods=["GET"])
def list_warehouses():
    warehouses = Warehouse.query.order_by(Warehouse.name).all()
    return jsonify([w.to_dict() for w in warehouses])


@bp.route("/api/warehouses/<int:wid>", methods=["GET"])
def get_warehouse(wid):
    w = db.get_or_404(Warehouse, wid)
    return jsonify(w.to_dict())


@bp.route("/api/warehouses", methods=["POST"])
def create_warehouse():
    data = request.get_json(silent=True) or {}
    required = ["name", "address", "lat", "lon"]
    missing = [f for f in required if not data.get(f) and data.get(f) != 0]
    if missing:
        return jsonify({"error": f"Обязательные поля: {', '.join(missing)}"}), 400

    w = Warehouse(
        name=data["name"],
        address=data["address"],
        lat=float(data["lat"]),
        lon=float(data["lon"]),
        contact=data.get("contact", ""),
    )
    db.session.add(w)
    db.session.commit()
    return jsonify(w.to_dict()), 201


@bp.route("/api/warehouses/<int:wid>", methods=["PUT"])
def update_warehouse(wid):
    w = db.get_or_404(Warehouse, wid)
    data = request.get_json(silent=True) or {}
    w.name = data.get("name", w.name)
    w.address = data.get("address", w.address)
    if "lat" in data:
        w.lat = float(data["lat"])
    if "lon" in data:
        w.lon = float(data["lon"])
    w.contact = data.get("contact", w.contact)
    db.session.commit()
    return jsonify(w.to_dict())


@bp.route("/api/warehouses/<int:wid>", methods=["DELETE"])
def delete_warehouse(wid):
    w = db.get_or_404(Warehouse, wid)
    db.session.delete(w)
    db.session.commit()
    return jsonify({"message": "Склад удалён"})
