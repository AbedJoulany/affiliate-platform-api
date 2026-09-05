from fastapi import APIRouter

from app.api.v1 import (
    ai_content,
    aliexpress,
    channels,
    dashboard,
    product_discovery,
    products,
    queue_stream,
    queues,
)
from app.auth.router import router as auth_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(product_discovery.router, prefix="/products", tags=["Product Discovery"])
api_router.include_router(products.router, prefix="/products", tags=["Products"])
api_router.include_router(channels.router, prefix="/channels", tags=["Telegram Channels"])
api_router.include_router(ai_content.router, prefix="/ai-content", tags=["AI Content"])
api_router.include_router(queue_stream.router, prefix="/queues", tags=["Queue"])
api_router.include_router(queues.router, prefix="/queues", tags=["Queue"])
api_router.include_router(aliexpress.router, prefix="/aliexpress", tags=["AliExpress"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
