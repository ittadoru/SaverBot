from .broad_gen import router as broadcast_router
from .broad_ad import router as ad_broadcast_router
from .broad_new import router as trial_broadcast_router


routers = [
    broadcast_router,
    ad_broadcast_router,
    trial_broadcast_router,
]
