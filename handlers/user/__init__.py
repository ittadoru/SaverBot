
from .about import router as about_router
from .start import router as start_router
from .promo import router as promo_router
from .subscribe import router as subscribe_router
from .myprofile import router as myprofile_router
from .download import router as download_router
from .myhistory import router as myhistory_router
from .referral import router as referral_router
from .referral_info import router as referral_info_router
from .crypto_payments import router as crypto_payments_router

routers = [
    about_router,
    start_router,
    promo_router,
    subscribe_router,
    myprofile_router,
    download_router,
    myhistory_router,
    referral_router,
    referral_info_router,
    crypto_payments_router,
]
