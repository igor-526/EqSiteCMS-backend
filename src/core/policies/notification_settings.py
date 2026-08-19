from core.schemas.users import UserOutDto

NOTIFICATION_ELIGIBILITY: dict[tuple[str, str], frozenset[str]] = {
    ("callback", "email"): frozenset({"ADMIN", "SUPERUSER"}),
}

# Notification-service owns these active catalog dimensions. The CMS currently
# exposes only callback/email, but valid private-service tuples for other
# channels must be filtered rather than treated as a broken response.
KNOWN_NOTIFICATION_EVENTS = frozenset({"callback"})
KNOWN_NOTIFICATION_CHANNELS = frozenset({"email", "vk", "sms"})


def eligible_notification_keys(actor: UserOutDto) -> set[tuple[str, str]]:
    actor_scopes = {scope.scope_name for scope in actor.scopes}
    return {
        key
        for key, required_scopes in NOTIFICATION_ELIGIBILITY.items()
        if actor_scopes & required_scopes
    }
