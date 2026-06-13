"""
Сервис управления складскими запасами.
Реализует правило «точка заказа» — автоматическое определение
товаров с критически низким остатком и расчёт рекомендуемого пополнения.
"""


def get_low_stock_items(stocks: list) -> list[dict]:
    """
    Возвращает список позиций, у которых остаток ниже порога (reorder_level).
    Для каждой позиции рассчитывает рекомендуемый объём пополнения:
    рекомендуется дозаказать до 2 × reorder_level.

    Параметры:
        stocks: список объектов Stock (SQLAlchemy)

    Возвращает:
        список словарей с деталями критических позиций
    """
    low_items = []
    for stock in stocks:
        if stock.quantity < stock.reorder_level:
            recommended_qty = max(0, 2 * stock.reorder_level - stock.quantity)
            low_items.append(
                {
                    "stock_id": stock.id,
                    "warehouse_id": stock.warehouse_id,
                    "warehouse_name": stock.warehouse.name if stock.warehouse else "—",
                    "product_id": stock.product_id,
                    "product_name": stock.product.name if stock.product else "—",
                    "product_unit": stock.product.unit if stock.product else "",
                    "quantity": stock.quantity,
                    "reorder_level": stock.reorder_level,
                    "recommended_qty": round(recommended_qty, 2),
                    "deficit": round(stock.reorder_level - stock.quantity, 2),
                }
            )
    return low_items
