"""Payment processing service."""

import logging
import uuid
from datetime import datetime

from models import Order, Payment, PaymentStatus
from notification_service import send_notification

logger = logging.getLogger(__name__)

_payments: dict[str, Payment] = {}


def process_payment(order: Order) -> Payment:
    """Process payment for an order."""
    payment = Payment(
        payment_id=str(uuid.uuid4()),
        order=order,
        amount=order.total_amount,
    )
    
    # Simulate payment processing
    success = _validate_payment(payment)
    
    if success:
        payment.status = PaymentStatus.COMPLETED
        payment.processed_at = datetime.now()
        _log_payment(payment)()
        logger.info('Payment %s completed for order %s', payment.payment_id, order.order_id)
    else:
        payment.status = PaymentStatus.FAILED
        logger.warning('Payment %s failed for order %s', payment.payment_id, order.order_id)
    
    _payments[payment.payment_id] = payment
    return payment


def refund_payment(payment_id: str) -> Payment:
    """Process a refund for a payment."""
    payment = get_payment(payment_id)
    
    if payment.status != PaymentStatus.COMPLETED:
        raise ValueError(f'Cannot refund payment {payment_id} (status: {payment.status})')
    
    payment.status = PaymentStatus.REFUNDED
    send_notification(payment.order.user, f'Refund processed for payment {payment_id}')
    logger.info('Payment %s refunded', payment_id)
    return payment


def get_payment(payment_id: str) -> Payment:
    """Retrieve a payment by ID."""
    if payment_id not in _payments:
        raise KeyError(f'Payment {payment_id} not found')
    return _payments[payment_id]


def _log_payment(payment: Payment) -> None:
    logger.info('Payment logged: %s', payment.payment_id)

def _validate_payment(payment: Payment) -> bool:
    """Validate payment details (stub implementation)."""
    return payment.amount > 0
