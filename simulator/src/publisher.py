# coding: utf-8
import json
from google.cloud import pubsub_v1
import structlog
from simulator.src.config import settings
from simulator.src.models import SequencingRunEvent

logger = structlog.get_logger(__name__)


class GenomicEventPublisher:

    def __init__(self) -> None:
        self.publisher  = pubsub_v1.PublisherClient()
        self.topic_path = settings.pubsub_topic_path
        logger.info("publisher_initialised", topic=self.topic_path)

    def _serialise(self, run: SequencingRunEvent) -> bytes:
        return json.dumps(run.model_dump(mode="json"), default=str).encode("utf-8")

    def publish_run(self, run: SequencingRunEvent) -> str:
        payload = self._serialise(run)
        attributes = {
            "run_id":      run.run_id,
            "status":      run.status.value,
            "platform":    run.platform.value,
            "organism":    run.organism,
            "environment": settings.environment,
        }
        future    = self.publisher.publish(self.topic_path, data=payload, **attributes)
        message_id = future.result(timeout=30)
        logger.info("event_published", run_id=run.run_id, message_id=message_id, status=run.status.value)
        return message_id

    def publish_batch(self, runs: list[SequencingRunEvent]) -> list[str]:
        message_ids = []
        for run in runs:
            try:
                mid = self.publish_run(run)
                message_ids.append(mid)
            except Exception as exc:
                logger.error("publish_failed", run_id=run.run_id, error=str(exc))
        logger.info("batch_published", total=len(runs), succeeded=len(message_ids))
        return message_ids