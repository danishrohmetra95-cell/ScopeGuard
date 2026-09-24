"""Tests for domain models."""

from models import User, Product, OrderItem, Order, OrderStatus


def test_user_creation():
    user = User(user_id='u1', username='testuser', email='test@example.com')
    assert user.username == 'testuser'
    assert user.is_active is True


def test_product_creation():
    product = Product(product_id='p1', name='Widget', price=9.99, stock=100)
    assert product.price == 9.99
    assert product.stock == 100


def test_order_total():
    user = User(user_id='u1', username='testuser', email='test@example.com')
    product = Product(product_id='p1', name='Widget', price=10.00, stock=50)
    item = OrderItem(product=product, quantity=3, unit_price=product.price)
    order = Order(order_id='o1', user=user, items=[item])
    assert order.total_amount == 30.00
    assert order.status == OrderStatus.PENDING
