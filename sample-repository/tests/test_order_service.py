"""Tests for order management."""

from models import Order, OrderItem, Product, User, OrderStatus
from order_service import create_order, get_order, cancel_order
from payment_service import process_payment


def test_create_order():
    user = User(user_id='u1', username='shopper', email='shop@test.com')
    product = Product(product_id='p1', name='Gadget', price=15.00, stock=20)
    order = create_order(user.user_id, [(product, 2)])
    assert order is not None


def test_cancel_order():
    user = User(user_id='u1', username='shopper', email='shop@test.com')
    product = Product(product_id='p1', name='Gadget', price=15.00, stock=20)
    order = create_order(user.user_id, [(product, 1)])
    cancelled = cancel_order(order.order_id)
    assert cancelled is not None


def test_get_order_not_found():
    result = get_order('nonexistent')
    assert result is None
