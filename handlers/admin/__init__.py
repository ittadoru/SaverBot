from .menu import router as menu_router
from .stats import router as stats_router
from .users import router as users_router
from .user_info import router as history_router
from .promo import router as promo_router
from .export_logs import router as log_router
from .tariff import router as tariff_router
from .export_tables import router as table_export_router
from .channels import router as channels_router
from .top_refferals import router as top_referrals_router
from .broadcast import routers as broadcast_routers

routers = [
    menu_router,
    stats_router,
    users_router,
    history_router,
    promo_router,
    log_router,
    tariff_router,
    table_export_router,
    channels_router,
    top_referrals_router
]

routers.extend(broadcast_routers)