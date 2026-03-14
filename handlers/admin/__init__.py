from .menu import router as menu_router
from .stats import router as stats_router
from .users import router as users_router
from .user_info import router as history_router
from .tariff import router as tariff_router
from .channels import router as channels_router
from .top_refferals import router as top_referrals_router
from .broadcast import routers as broadcast_routers

routers = [
    menu_router,
    stats_router,
    users_router,
    history_router,
    tariff_router,
    channels_router,
    top_referrals_router
]

routers.extend(broadcast_routers)
