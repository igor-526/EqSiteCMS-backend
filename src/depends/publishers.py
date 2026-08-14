from containers import container
from core.protocols.publishers import CallbackRequestEventPublisherProtocol


def get_callback_request_event_publisher() -> CallbackRequestEventPublisherProtocol:
    return container.callback_request_event_publisher()
