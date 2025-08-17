from .about import router as about_router
from .start import router as start_router
from .promo import router as promo_router
from .subscribe import router as subscribe_router
from .myprofile import router as myprofile_router
from .menu import router as menu_router
from .download import router as download_router


routers = [
    about_router,
    start_router,
    promo_router,
    subscribe_router,
    myprofile_router,
    menu_router,
    download_router
]
