"Order management service."

import logging
import uuid

from models import Order, OrderItem, OrderStatus, Product, User
from user_service import get_user
from payment_service import process_payment
from notification_service import send_order_confirmation, send_notification

logger = logging.getLogger(__name__)

_orders: dict[str, Order] = {}


def create_order(user_id: str, items: list[tuple[Product, int]]) -> Order:
    "Create a new order for a user."
    user = get_user(user_id)

    order_items = [
        OrderItem(product=product, quantity=qty, unit_price=product.price)
        for product, qty in items
    ]

    order = Order(
        order_id=str(uuid.uuid4()),
        user=user,
        items=order_items,
    )

    _orders[order.order_id] = order
    logger.info('Created order %s for user %s', order.order_id, user.username)

    return order


def confirm_order(order_id: str) -> Order:
    "Confirm an order and process payment."
    order = get_order(order_id)

    if order.status != OrderStatus.PENDING:
        raise ValueError(f'Order {order_id} cannot be confirmed (status: {order.status})')

    payment = process_payment(order)

    if payment.status.value == 'completed':
        order.status = OrderStatus.CONFIRMED
        send_order_confirmation(order)
        logger.info('Order %s confirmed', order_id)
    else:
        logger.warning('Payment failed for order %s', order_id)
        send_notification(order.user, f'Payment failed for order {order_id}')

    return order


def cancel_order(order_id: str) -> Order:
    "Cancel an existing order."
    order = get_order(order_id)
    if order.status == OrderStatus.CONFIRMED:
        logger.warning('Cancelling confirmed order %s', order_id)
    order.status = OrderStatus.CANCELLED
    send_notification(order.user, f'Order {order_id} has been cancelled.')
    logger.info('Order %s cancelled', order_id)
    return order


def get_order(order_id: str) -> Order:
    "Retrieve an order by ID."
    if order_id not in _orders:
        raise KeyError(f'Order {order_id} not found')
    return _orders[order_id]


def list_orders(user_id: str | None = None) -> list[Order]:
    "List all orders, optionally filtered by user."
    orders = list(_orders.values())
    if user_id:
        orders = [o for o in orders if o.user.user_id == user_id]
    return orders
