from flask import Blueprint, request, jsonify
from models import db, Product, Stock

bp = Blueprint("products", __name__)


@bp.route("/api/products", methods=["GET"])
def list_products():
    products = Product.query.order_by(Product.name).all()
    result = []
    for p in products:
        d = p.to_dict()
        d["stocks"] = [s.to_dict() for s in p.stocks]
        result.append(d)
    return jsonify(result)


@bp.route("/api/products/<int:pid>", methods=["GET"])
def get_product(pid):
    p = db.get_or_404(Product, pid)
    d = p.to_dict()
    d["stocks"] = [s.to_dict() for s in p.stocks]
    return jsonify(d)


@bp.route("/api/products", methods=["POST"])
def create_product():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "Поле 'name' обязательно"}), 400
    p = Product(name=data["name"], unit=data.get("unit", "шт"))
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201


@bp.route("/api/products/<int:pid>", methods=["PUT"])
def update_product(pid):
    p = db.get_or_404(Product, pid)
    data = request.get_json(silent=True) or {}
    p.name = data.get("name", p.name)
    p.unit = data.get("unit", p.unit)
    db.session.commit()
    return jsonify(p.to_dict())


@bp.route("/api/products/<int:pid>", methods=["DELETE"])
def delete_product(pid):
    p = db.get_or_404(Product, pid)
    db.session.delete(p)
    db.session.commit()
    return jsonify({"message": "Товар удалён"})
