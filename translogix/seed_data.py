"""Тестовые данные: 2 склада, 3 товара, 5 заказов."""
from models import Warehouse, Product, Stock, Order
from datetime import datetime, timedelta


def seed(db):
    # --- Склады (Москва) ---
    w1 = Warehouse(
        name="Склад Север",
        address="Москва, Дмитровское ш., 107",
        lat=55.8886,
        lon=37.5384,
        contact="+7 (495) 111-22-33",
    )
    w2 = Warehouse(
        name="Склад Юг",
        address="Москва, Варшавское ш., 125",
        lat=55.6200,
        lon=37.6200,
        contact="+7 (495) 444-55-66",
    )
    db.session.add_all([w1, w2])
    db.session.flush()

    # --- Товары ---
    p1 = Product(name="Ноутбук Lenovo ThinkPad", unit="шт")
    p2 = Product(name="Принтер Canon LBP", unit="шт")
    p3 = Product(name="Бумага офисная A4", unit="пачка")
    db.session.add_all([p1, p2, p3])
    db.session.flush()

    # --- Остатки ---
    stocks = [
        Stock(warehouse_id=w1.id, product_id=p1.id, quantity=12, reorder_level=10),
        Stock(warehouse_id=w1.id, product_id=p2.id, quantity=4, reorder_level=8),   # низкий
        Stock(warehouse_id=w1.id, product_id=p3.id, quantity=50, reorder_level=20),
        Stock(warehouse_id=w2.id, product_id=p1.id, quantity=7, reorder_level=10),  # низкий
        Stock(warehouse_id=w2.id, product_id=p2.id, quantity=15, reorder_level=8),
        Stock(warehouse_id=w2.id, product_id=p3.id, quantity=5, reorder_level=20),  # низкий
    ]
    db.session.add_all(stocks)
    db.session.flush()

    # --- Заказы (точки доставки по Москве) ---
    base = datetime.utcnow()
    orders = [
        Order(
            product_id=p1.id, quantity=2,
            delivery_address="Москва, Тверская ул., 1",
            delivery_lat=55.7573, delivery_lon=37.6175,
            status="new", created_at=base - timedelta(hours=3),
        ),
        Order(
            product_id=p3.id, quantity=10,
            delivery_address="Москва, Арбат ул., 10",
            delivery_lat=55.7520, delivery_lon=37.5960,
            status="new", created_at=base - timedelta(hours=2),
        ),
        Order(
            product_id=p2.id, quantity=1,
            delivery_address="Москва, Ленинский просп., 60",
            delivery_lat=55.6993, delivery_lon=37.5665,
            status="new", created_at=base - timedelta(hours=1),
        ),
        Order(
            product_id=p1.id, quantity=3,
            delivery_address="Москва, пр-т Мира, 98",
            delivery_lat=55.8023, delivery_lon=37.6378,
            status="new", created_at=base - timedelta(minutes=40),
        ),
        Order(
            product_id=p3.id, quantity=5,
            delivery_address="Москва, Кутузовский просп., 30",
            delivery_lat=55.7411, delivery_lon=37.5264,
            status="completed", created_at=base - timedelta(days=1),
        ),
    ]
    db.session.add_all(orders)
    db.session.commit()
