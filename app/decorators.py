import json
import time
import logging
import functools

logger = logging.getLogger(__name__)


def log_rpc_method(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        method_name = func.__name__
        ext_id = kwargs.get("ext_id", "unknown")

        # REQUEST лог
        logger.info(
            "[%s] REQUEST | ext_id=%s | params=%s",
            method_name,
            ext_id,
            json.dumps(kwargs, default=str),
        )

        try:
            result = func(*args, **kwargs)
            elapsed = round((time.time() - start_time) * 1000, 2)

            # RESPONSE лог
            logger.info(
                "[%s] RESPONSE | ext_id=%s | time=%sms | result=%s",
                method_name,
                ext_id,
                elapsed,
                repr(result)[:300],
            )
            return result

        except Exception as exc:
            elapsed = round((time.time() - start_time) * 1000, 2)
            logger.error(
                "[%s] ERROR | ext_id=%s | time=%sms | error=%s",
                method_name,
                ext_id,
                elapsed,
                str(exc),
            )
            raise

    return wrapper
