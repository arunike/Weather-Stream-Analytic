import logging
from datetime import datetime, timezone
from typing import Dict

from celery import shared_task

from .cache.redis_client import get_redis_client

logger = logging.getLogger(__name__)


@shared_task
def record_async_audit(event: Dict) -> None:
    redis_client = get_redis_client()
    payload = dict(event)
    payload.setdefault('timestamp', datetime.now(timezone.utc).timestamp())
    try:
        redis_client.lpush('fraud_state:async_audits', str(payload))
        redis_client.ltrim('fraud_state:async_audits', 0, 199)
        redis_client.expire('fraud_state:async_audits', 86400)
    except Exception as exc:
        logger.warning("Failed to record async audit: %s", exc)
