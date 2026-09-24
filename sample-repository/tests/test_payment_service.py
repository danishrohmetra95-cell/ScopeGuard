"""Tests for payment processing."""

from models import Order, OrderItem, Product, User, PaymentStatus
from payment_service import process_payment, refund_payment, get_payment


def test_process_payment_creates_payment():
    user = User(user_id='u1', username='buyer', email='buyer@test.com')
    product = Product(product_id='p1', name='Widget', price=25.00, stock=10)
    item = OrderItem(product=product, quantity=2, unit_price=product.price)
    order = Order(order_id='o1', user=user, items=[item])
    payment = process_payment(order)
    assert payment is not None
    assert payment.amount == 50.00


def test_refund_payment():
    user = User(user_id='u1', username='buyer', email='buyer@test.com')
    product = Product(product_id='p1', name='Widget', price=10.00, stock=5)
    item = OrderItem(product=product, quantity=1, unit_price=product.price)
    order = Order(order_id='o2', user=user, items=[item])
    payment = process_payment(order)
    refunded = refund_payment(payment.payment_id)
    assert refunded is not None


def test_get_payment_not_found():
    result = get_payment('nonexistent')
    assert result is None
