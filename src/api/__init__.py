from .auth import router as auth_router
from .breeds import router as breeds_router
from .callback_request import router as callback_request_router
from .coat_color import router as coat_color_router
from .emails import router as emails_router
from .horse_owner import router as horse_owner_router
from .horse_service import router as horse_service_router
from .horse_service_relations import router as horse_service_relations_router
from .horses import router as horses_router
from .news import router as news_router
from .photos import router as photos_router
from .prices import router as prices_router
from .service_users import router as service_users_router
from .site_settings import router as site_settings_router
from .users import router as users_router

__all__ = [
    "user_management_router",
    "auth_router",
    "breeds_router",
    "callback_request_router",
    "coat_color_router",
    "emails_router",
    "horse_owner_router",
    "horse_service_router",
    "horse_service_relations_router",
    "horses_router",
    "news_router",
    "photos_router",
    "prices_router",
    "service_users_router",
    "site_settings_router",
    "users_router",
]
from .user_management import router as user_management_router
