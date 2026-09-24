"""Domain models for the sample e-commerce application."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OrderStatus(Enum):
    """Possible states of an order."""
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    SHIPPED = 'shipped'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'


class PaymentStatus(Enum):
    """Possible payment states."""
    PENDING = 'pending'
    COMPLETED = 'completed'
    FAILED = 'failed'
    REFUNDED = 'refunded'


@dataclass
class User:
    """Represents a customer."""
    user_id: str
    username: str
    email: str
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True


@dataclass
class Product:
    """Represents a product in the catalog."""
    product_id: str
    name: str
    price: float
    stock: int = 0
    category: str = 'general'


@dataclass
class OrderItem:
    """A single item within an order."""
    product: Product
    quantity: int
    unit_price: float

    @property
    def total_price(self) -> float:
        return self.unit_price * self.quantity


@dataclass
class Order:
    """Represents a customer order."""
    order_id: str
    user: User
    items: list[OrderItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def total_amount(self) -> float:
        return sum(item.total_price for item in self.items)


@dataclass
class Payment:
    """Represents a payment transaction."""
    payment_id: str
    order: Order
    amount: float
    status: PaymentStatus = PaymentStatus.PENDING
    processed_at: datetime | None = None
