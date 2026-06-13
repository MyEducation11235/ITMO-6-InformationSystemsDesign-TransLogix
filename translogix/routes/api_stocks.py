from flask import Blueprint, request, jsonify
from models import db, Stock, Warehouse, Product

bp = Blueprint("stocks", __name__)


@bp.route("/api/stocks", methods=["GET"])
def list_stocks():
    warehouse_id = request.args.get("warehouse_id", type=int)
    product_id = request.args.get("product_id", type=int)
    q = Stock.query
    if warehouse_id:
        q = q.filter_by(warehouse_id=warehouse_id)
    if product_id:
        q = q.filter_by(product_id=product_id)
    stocks = q.all()
    return jsonify([s.to_dict() for s in stocks])


@bp.route("/api/stocks", methods=["POST"])
def upsert_stock():
    """Создаёт или обновляет запись остатка товара на складе."""
    data = request.get_json(silent=True) or {}
    required = ["warehouse_id", "product_id", "quantity"]
    missing = [f for f in required if data.get(f) is None]
    if missing:
        return jsonify({"error": f"Обязательные поля: {', '.join(missing)}"}), 400

    warehouse = db.get_or_404(Warehouse, data["warehouse_id"])
    product = db.get_or_404(Product, data["product_id"])

    stock = Stock.query.filter_by(
        warehouse_id=warehouse.id, product_id=product.id
    ).first()

    if stock:
        stock.quantity = float(data["quantity"])
        if "reorder_level" in data:
            stock.reorder_level = float(data["reorder_level"])
    else:
        stock = Stock(
            warehouse_id=warehouse.id,
            product_id=product.id,
            quantity=float(data["quantity"]),
            reorder_level=float(data.get("reorder_level", 10)),
        )
        db.session.add(stock)

    db.session.commit()
    return jsonify(stock.to_dict()), 200


@bp.route("/api/stocks/<int:sid>", methods=["PUT"])
def update_stock(sid):
    stock = db.get_or_404(Stock, sid)
    data = request.get_json(silent=True) or {}
    if "quantity" in data:
        stock.quantity = float(data["quantity"])
    if "reorder_level" in data:
        stock.reorder_level = float(data["reorder_level"])
    db.session.commit()
    return jsonify(stock.to_dict())


@bp.route("/api/stocks/low", methods=["GET"])
def low_stocks():
    """Возвращает позиции с остатком ниже порога пополнения."""
    from services.inventory import get_low_stock_items
    all_stocks = Stock.query.all()
    return jsonify(get_low_stock_items(all_stocks))
