from src.api.auth import router as auth_router
from src.api.trading import router as trading_router
from src.api.wallet import router as wallet_router

__all__ = [
    "auth_router",
    "trading_router",
    "wallet_router",
]
