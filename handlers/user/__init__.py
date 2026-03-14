
from .about import router as about_router
from .start import router as start_router
from .subscribe import router as subscribe_router
from .tokens import router as tokens_router
from .download import router as download_router
from .myhistory import router as myhistory_router
from .referral import router as referral_router

routers = [
    about_router,
    start_router,
    subscribe_router,
    tokens_router,
    download_router,
    myhistory_router,
    referral_router,
]
