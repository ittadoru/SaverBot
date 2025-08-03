from .about import router as about_router
from .help import router as help_router
from .start import router as start_router
from .download import router as download_router
from .myhistory import router as myhistory_router
from .promo import router as promo_router

routers = [
    about_router,
    help_router,
    start_router,
    download_router,
    myhistory_router,
    promo_router
]
