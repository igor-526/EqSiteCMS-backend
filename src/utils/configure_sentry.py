import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from settings import sentry_settings


def configure_sentry() -> None:
    if not sentry_settings.sentry_enabled:
        return

    sentry_sdk.init(
        dsn=sentry_settings.sentry_dsn,
        environment=sentry_settings.sentry_environment,
        release=sentry_settings.sentry_release,
        traces_sample_rate=sentry_settings.sentry_traces_sample_rate,
        send_default_pii=False,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
    )
