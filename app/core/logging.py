import logging
import sys


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Set logger levels
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)


logger = logging.getLogger("asemanha_backend")
