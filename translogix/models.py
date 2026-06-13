from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Warehouse(db.Model):
    __tablename__ = "warehouses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(500), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    contact = db.Column(db.String(200))

    stocks = db.relationship("Stock", backref="warehouse", lazy=True, cascade="all, delete-orphan")
    route_stops = db.relationship("RouteStop", backref="warehouse", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "lat": self.lat,
            "lon": self.lon,
            "contact": self.contact or "",
        }


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    unit = db.Column(db.String(50), nullable=False, default="шт")

    stocks = db.relationship("Stock", backref="product", lazy=True, cascade="all, delete-orphan")
    orders = db.relationship("Order", backref="product", lazy=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "unit": self.unit}


class Stock(db.Model):
    __tablename__ = "stocks"

    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0)
    reorder_level = db.Column(db.Float, nullable=False, default=10)

    def to_dict(self):
        return {
            "id": self.id,
            "warehouse_id": self.warehouse_id,
            "warehouse_name": self.warehouse.name if self.warehouse else None,
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else None,
            "product_unit": self.product.unit if self.product else None,
            "quantity": self.quantity,
            "reorder_level": self.reorder_level,
            "low_stock": self.quantity < self.reorder_level,
        }


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    delivery_address = db.Column(db.String(500), nullable=False)
    delivery_lat = db.Column(db.Float, nullable=False)
    delivery_lon = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), nullable=False, default="new")  # new / in_route / completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    route_stops = db.relationship("RouteStop", backref="order", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else None,
            "product_unit": self.product.unit if self.product else None,
            "quantity": self.quantity,
            "delivery_address": self.delivery_address,
            "delivery_lat": self.delivery_lat,
            "delivery_lon": self.delivery_lon,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Route(db.Model):
    __tablename__ = "routes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    confirmed = db.Column(db.Boolean, default=False)
    total_distance = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    stops = db.relationship("RouteStop", backref="route", lazy=True, order_by="RouteStop.stop_order", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "confirmed": self.confirmed,
            "total_distance": self.total_distance,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "stops": [s.to_dict() for s in self.stops],
        }


class RouteStop(db.Model):
    __tablename__ = "route_stops"

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id"), nullable=False)
    stop_order = db.Column(db.Integer, nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=True)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(500), nullable=False)
    stop_type = db.Column(db.String(50), nullable=False)  # 'warehouse' or 'delivery'

    def to_dict(self):
        return {
            "id": self.id,
            "route_id": self.route_id,
            "stop_order": self.stop_order,
            "order_id": self.order_id,
            "warehouse_id": self.warehouse_id,
            "lat": self.lat,
            "lon": self.lon,
            "address": self.address,
            "stop_type": self.stop_type,
        }
