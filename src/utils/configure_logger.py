import logging


def configure_logger(
    logger_root_name: str, logger_prefix_output: str, advanced: bool = True
) -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if advanced:
        logging.basicConfig(
            format=f"{logger_prefix_output}:\n    TIME: %(asctime)s\n    LOGLEVEL: %(levelname)s\n    FIlENAME: %(name)s\n    MESSAGE: %(message)s",
            level=logging.INFO,
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
        )

    logger = logging.getLogger(logger_root_name)
    logger.info("Logger has configured.")
