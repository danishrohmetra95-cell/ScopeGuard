"""REST API endpoints for the sample e-commerce application."""

from fastapi import FastAPI, HTTPException

from user_service import create_user, get_user, list_users, deactivate_user
from order_service import create_order, get_order, confirm_order, cancel_order, list_orders
from payment_service import refund_payment

app = FastAPI(title='Sample E-Commerce API')


@app.get('/health')
async def health_check():
    """Health check endpoint."""
    return {'status': 'healthy'}


@app.get('/users')
async def get_users():
    """List all users."""
    return list_users()


@app.get('/users/{user_id}')
async def get_user_detail(user_id: str):
    """Get user details."""
    try:
        return get_user(user_id)
    except KeyError:
        raise HTTPException(status_code=404, detail='User not found')


@app.post('/users')
async def create_new_user(user_id: str, username: str, email: str):
    """Create a new user."""
    try:
        return create_user(user_id, username, email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post('/users/{user_id}/deactivate')
async def deactivate(user_id: str):
    """Deactivate a user account."""
    try:
        return deactivate_user(user_id)
    except KeyError:
        raise HTTPException(status_code=404, detail='User not found')


@app.get('/orders')
async def get_orders(user_id: str | None = None):
    """List all orders."""
    return list_orders(user_id)


@app.get('/orders/{order_id}')
async def get_order_detail(order_id: str):
    """Get order details."""
    try:
        return get_order(order_id)
    except KeyError:
        raise HTTPException(status_code=404, detail='Order not found')


@app.post('/orders/{order_id}/confirm')
async def confirm(order_id: str):
    """Confirm an order."""
    try:
        return confirm_order(order_id)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post('/orders/{order_id}/cancel')
async def cancel(order_id: str):
    """Cancel an order."""
    try:
        return cancel_order(order_id)
    except KeyError:
        raise HTTPException(status_code=404, detail='Order not found')


@app.post('/payments/{payment_id}/refund')
async def refund(payment_id: str):
    """Process a refund."""
    try:
        return refund_payment(payment_id)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
