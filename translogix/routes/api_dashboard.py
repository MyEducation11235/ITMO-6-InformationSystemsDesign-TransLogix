from flask import Blueprint, jsonify
from models import db, Order, Stock, Route, Warehouse
from services.inventory import get_low_stock_items
from datetime import date

bp = Blueprint("dashboard", __name__)


@bp.route("/api/dashboard", methods=["GET"])
def dashboard():
    """Агрегированные данные для дашборда логиста."""
    total_orders = Order.query.count()
    new_orders = Order.query.filter_by(status="new").count()
    in_route_orders = Order.query.filter_by(status="in_route").count()
    completed_orders = Order.query.filter_by(status="completed").count()

    total_warehouses = Warehouse.query.count()
    all_stocks = Stock.query.all()
    low_items = get_low_stock_items(all_stocks)

    today_routes = Route.query.filter(
        db.func.date(Route.created_at) == date.today()
    ).count()
    total_routes = Route.query.count()
    confirmed_routes = Route.query.filter_by(confirmed=True).count()

    recent_orders = (
        Order.query.order_by(Order.created_at.desc()).limit(5).all()
    )

    warehouses = Warehouse.query.all()
    warehouse_markers = [
        {"id": w.id, "name": w.name, "lat": w.lat, "lon": w.lon, "address": w.address}
        for w in warehouses
    ]
    active_orders_markers = [
        {
            "id": o.id,
            "lat": o.delivery_lat,
            "lon": o.delivery_lon,
            "address": o.delivery_address,
            "status": o.status,
            "product": o.product.name if o.product else "",
        }
        for o in Order.query.filter(Order.status != "completed").all()
    ]

    return jsonify(
        {
            "orders": {
                "total": total_orders,
                "new": new_orders,
                "in_route": in_route_orders,
                "completed": completed_orders,
            },
            "warehouses": {"total": total_warehouses},
            "inventory": {"low_stock_count": len(low_items), "low_stock_items": low_items},
            "routes": {
                "total": total_routes,
                "today": today_routes,
                "confirmed": confirmed_routes,
            },
            "recent_orders": [o.to_dict() for o in recent_orders],
            "map": {
                "warehouses": warehouse_markers,
                "orders": active_orders_markers,
            },
        }
    )
