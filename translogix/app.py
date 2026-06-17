import os
import sys
import logging

from flask import Flask, render_template
from flask_cors import CORS
from models import db

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, "translogix.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "translogix-secret-key-2025")

    CORS(app)
    db.init_app(app)

    from routes.api_warehouses import bp as warehouses_bp
    from routes.api_products   import bp as products_bp
    from routes.api_stocks     import bp as stocks_bp
    from routes.api_orders     import bp as orders_bp
    from routes.api_routes     import bp as routes_bp
    from routes.api_dashboard  import bp as dashboard_bp

    app.register_blueprint(warehouses_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(stocks_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(routes_bp)
    app.register_blueprint(dashboard_bp)

    @app.route("/")
    def index():
        return render_template("dashboard.html")

    @app.route("/warehouses")
    def warehouses_page():
        return render_template("warehouses.html")

    @app.route("/products")
    def products_page():
        return render_template("products.html")

    @app.route("/orders")
    def orders_page():
        return render_template("orders.html")

    @app.route("/route-builder")
    def route_builder_page():
        return render_template("route_builder.html")

    @app.route("/routes")
    def routes_page():
        return render_template("routes.html")

    @app.errorhandler(404)
    def not_found(e):
        from flask import request, jsonify
        if request.path.startswith("/api/"):
            return jsonify({"error": "Ресурс не найден"}), 404
        return render_template("dashboard.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import request, jsonify
        logger.error("Server error: %s", e)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500
        return render_template("dashboard.html"), 500

    with app.app_context():
        db.create_all()
        _migrate_db()
        _seed_if_empty()

    return app


def _migrate_db():
    """Add new columns to existing tables without losing data (SQLite safe)."""
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE routes ADD COLUMN status VARCHAR(50) DEFAULT 'pending'",
        "ALTER TABLE route_stops ADD COLUMN delivery_result VARCHAR(20)",
    ]
    with db.engine.connect() as conn:
        for stmt in migrations:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass  # Column already exists — safe to ignore


def _seed_if_empty():
    from models import Warehouse
    if Warehouse.query.count() == 0:
        try:
            from seed_data import seed
            seed(db)
        except Exception as exc:
            logger.error("Seed error: %s", exc)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(__file__))
    port = int(os.environ.get("PORT", 5000))
    application = create_app()
    application.run(host="0.0.0.0", port=port, debug=False)
