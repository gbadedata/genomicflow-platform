# coding: utf-8
import json
import signal
import structlog
from google.cloud import pubsub_v1
from pipeline.src.bq_writer import BigQueryWriter
from pipeline.src.validator import validate_record
from simulator.src.config import settings

logger   = structlog.get_logger(__name__)
_running = True


def _handle_signal(signum, frame):
    global _running
    _running = False
    logger.info("pipeline_shutdown_signal")


def run_pipeline(max_messages: int = 0, dry_run: bool = False) -> dict:
    global _running
    _running = True

    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    subscriber = pubsub_v1.SubscriberClient()
    sub_path   = settings.pubsub_subscription_path
    writer     = BigQueryWriter()

    total = processed = quarantined = failed = 0

    logger.info("pipeline_started", subscription=sub_path, max_messages=max_messages)

    while _running:
        try:
            response = subscriber.pull(
                request={"subscription": sub_path, "max_messages": 10},
                timeout=10,
            )

            if not response.received_messages:
                if max_messages and total >= max_messages:
                    break
                if not _running:
                    break
                logger.info("no_messages_waiting", total_so_far=total)
                break

            for received in response.received_messages:
                try:
                    data   = json.loads(received.message.data.decode("utf-8"))
                    run_id = data.get("run_id", "unknown")
                    result = validate_record(data)

                    if dry_run:
                        logger.info(
                            "dry_run_message",
                            run_id=run_id,
                            status=data.get("status"),
                            completeness=result.completeness_score,
                            would_quarantine=result.quarantine,
                        )
                    elif result.quarantine:
                        logger.warning(
                            "record_quarantined",
                            run_id=run_id,
                            reason=result.rejection_reason,
                        )
                        quarantined += 1
                    else:
                        run_ok = writer.write_run(data, result.completeness_score)
                        if run_ok:
                            writer.write_variants(data.get("variants", []), run_id)
                            writer.write_quality_metrics(data.get("quality_metrics", []), run_id)
                            processed += 1
                            logger.info(
                                "message_processed",
                                run_id=run_id,
                                status=data.get("status"),
                                completeness=result.completeness_score,
                            )
                        else:
                            failed += 1

                    subscriber.acknowledge(
                        request={"subscription": sub_path, "ack_ids": [received.ack_id]}
                    )
                    total += 1

                except Exception as exc:
                    logger.error("message_error", error=str(exc))
                    failed += 1
                    total += 1

                if max_messages and total >= max_messages:
                    _running = False
                    break

        except Exception as exc:
            logger.error("pipeline_error", error=str(exc))
            break

    summary = {
        "total":       total,
        "processed":   processed,
        "quarantined": quarantined,
        "failed":      failed,
    }
    logger.info("pipeline_stopped", **summary)
    return summary


if __name__ == "__main__":
    run_pipeline(max_messages=50)