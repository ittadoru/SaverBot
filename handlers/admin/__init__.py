from .menu import router as menu_router
from .stats import router as stats_router
from .users import router as users_router
from .broadcast import router as broadcast_router
from .cleanup import router as cleanup_router
from .history import router as history_router
from .ad_broadcast import router as ad_broadcast_router
from .promo import router as promo_router
from .log_export import router as log_router
from .tariff import router as tariff_router

routers = [
    menu_router,
    stats_router,
    users_router,
    broadcast_router,
    ad_broadcast_router,
    cleanup_router,
    history_router,
    promo_router,
    log_router,
    tariff_router
]
