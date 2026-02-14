import json
import logging
from datetime import datetime


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data"):
            log_entry.update(record.extra_data)
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger("yoyo")
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Quiet noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    return root_logger
