from fastapi import APIRouter

from app.api.v1 import affiliates, campaigns, channels, conversions, products
from app.auth.router import router as auth_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(affiliates.router, prefix="/affiliates", tags=["Affiliates"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"])
api_router.include_router(conversions.router, prefix="/conversions", tags=["Conversions"])
api_router.include_router(products.router, prefix="/products", tags=["Products"])
api_router.include_router(channels.router, prefix="/channels", tags=["Telegram Channels"])
