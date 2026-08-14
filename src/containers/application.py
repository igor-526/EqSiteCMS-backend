from dependency_injector import containers, providers

from clients.nats import NatsJetstreamClient
from clients.nats.publisher import CallbackRequestEventPublisher
from settings import nats_settings as nats_settings_instance


class ApplicationContainer(containers.DeclarativeContainer):
    nats_settings = providers.Object(nats_settings_instance)

    nats_client = providers.Singleton(
        NatsJetstreamClient,
        settings=nats_settings,
    )

    callback_request_event_publisher = providers.Singleton(
        CallbackRequestEventPublisher,
        client=nats_client,
        settings=nats_settings,
    )
