# coding: utf-8
"""
Streaming pipeline: pull from Pub/Sub, validate, write to BigQuery.

Every message ends in exactly one of three places:

* processed   - all rows written to BigQuery, then acked;
* rejected    - stored in the rejected_records table with the reason and the
                original payload, then acked (retrying would not fix it);
* retried     - nacked, because a write failed. Pub/Sub redelivers it with
                back-off and, after max_delivery_attempts, moves it to the
                dead-letter topic.

A message is only acked once its outcome is stored, so a failed write can no
longer lose data.
"""
import json
import signal
from enum import Enum

import structlog
from google.cloud import pubsub_v1

from pipeline.src.bq_writer import BigQueryWriter
from pipeline.src.validator import validate_record
from simulator.src.config import settings

logger   = structlog.get_logger(__name__)
_running = True


class Outcome(str, Enum):
    PROCESSED = "processed"
    REJECTED  = "rejected"
    RETRY     = "retry"
    DRY_RUN   = "dry_run"


# Outcomes after which the message is acknowledged. RETRY is nacked.
ACK_OUTCOMES = {Outcome.PROCESSED, Outcome.REJECTED, Outcome.DRY_RUN}


def _handle_signal(signum, frame):
    global _running
    _running = False
    logger.info("pipeline_shutdown_signal")


def handle_message(received, writer: BigQueryWriter, dry_run: bool = False) -> Outcome:
    """Decide and store the outcome of one Pub/Sub message. Never raises."""
    message    = received.message
    message_id = getattr(message, "message_id", "") or received.ack_id
    attempt    = getattr(received, "delivery_attempt", None) or None
    raw        = message.data.decode("utf-8", errors="replace")

    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError(f"payload is a JSON {type(data).__name__}, not an object")
    except ValueError as exc:
        reason = f"payload is not a valid JSON object: {exc}"
        logger.warning("record_unparseable", message_id=message_id, reason=reason)
        if dry_run:
            return Outcome.DRY_RUN
        stored = writer.write_rejected(
            message_id, "UNPARSEABLE", reason, raw, delivery_attempt=attempt
        )
        return Outcome.REJECTED if stored else Outcome.RETRY

    run_id = data.get("run_id") or None
    result = validate_record(data)

    if dry_run:
        logger.info(
            "dry_run_message",
            run_id=run_id,
            status=data.get("status"),
            completeness=result.completeness_score,
            would_reject=result.quarantine,
        )
        return Outcome.DRY_RUN

    if result.quarantine:
        logger.warning("record_rejected", run_id=run_id, reason=result.rejection_reason)
        stored = writer.write_rejected(
            message_id, "VALIDATION", result.rejection_reason, raw,
            run_id=run_id, delivery_attempt=attempt,
        )
        return Outcome.REJECTED if stored else Outcome.RETRY

    try:
        ok = (
            writer.write_run(data, result.completeness_score)
            and writer.write_variants(data.get("variants") or [], run_id)
            and writer.write_quality_metrics(data.get("quality_metrics") or [], run_id)
        )
    except Exception as exc:  # network errors, quota, bad credentials
        logger.error("bq_write_error", run_id=run_id, error=str(exc))
        ok = False

    if not ok:
        logger.error("message_will_retry", run_id=run_id, delivery_attempt=attempt)
        return Outcome.RETRY

    logger.info(
        "message_processed",
        run_id=run_id,
        status=data.get("status"),
        completeness=result.completeness_score,
        warnings=result.failed_rules,
    )
    return Outcome.PROCESSED


def run_pipeline(max_messages: int = 0, dry_run: bool = False) -> dict:
    global _running
    _running = True

    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    subscriber = pubsub_v1.SubscriberClient()
    sub_path   = settings.pubsub_subscription_path
    writer     = BigQueryWriter()

    counts = {outcome: 0 for outcome in Outcome}
    total  = 0

    logger.info("pipeline_started", subscription=sub_path, max_messages=max_messages)

    while _running:
        try:
            response = subscriber.pull(
                request={"subscription": sub_path, "max_messages": 10},
                timeout=10,
            )
        except Exception as exc:
            logger.error("pipeline_error", error=str(exc))
            break

        if not response.received_messages:
            logger.info("no_messages_waiting", total_so_far=total)
            break

        for received in response.received_messages:
            outcome = handle_message(received, writer, dry_run=dry_run)
            counts[outcome] += 1
            total += 1

            if outcome in ACK_OUTCOMES:
                subscriber.acknowledge(
                    request={"subscription": sub_path, "ack_ids": [received.ack_id]}
                )
            else:
                # Deadline 0 = nack: redeliver with back-off, then dead-letter.
                subscriber.modify_ack_deadline(
                    request={
                        "subscription": sub_path,
                        "ack_ids": [received.ack_id],
                        "ack_deadline_seconds": 0,
                    }
                )

            if max_messages and total >= max_messages:
                _running = False
                break

    summary = {"total": total, **{o.value: n for o, n in counts.items()}}
    logger.info("pipeline_stopped", **summary)
    return summary


if __name__ == "__main__":
    run_pipeline(max_messages=50)
