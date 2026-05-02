# coding: utf-8
import signal
import time
import structlog
from simulator.src.generator import generate_run
from simulator.src.publisher import GenomicEventPublisher

logger  = structlog.get_logger(__name__)
_running = True


def _handle_signal(signum, frame):
    global _running
    _running = False
    logger.info("shutdown_signal_received")


def run_simulator(interval_seconds: float = 5.0, max_runs: int = 0, dry_run: bool = False) -> dict:
    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    publisher = None if dry_run else GenomicEventPublisher()
    total = passed = failed = quarantined = 0

    logger.info("simulator_started", interval=interval_seconds, max_runs=max_runs, dry_run=dry_run)

    while _running:
        try:
            run = generate_run()
            if dry_run:
                logger.info("dry_run_event", run_id=run.run_id, status=run.status.value,
                            platform=run.platform.value, completeness=run.completeness_score)
            else:
                publisher.publish_run(run)

            total += 1
            if run.status.value == "PASSED":
                passed += 1
            elif run.status.value == "FAILED":
                failed += 1
            else:
                quarantined += 1

            if max_runs and total >= max_runs:
                break

            time.sleep(interval_seconds)

        except Exception as exc:
            logger.error("simulator_error", error=str(exc))
            time.sleep(interval_seconds)

    summary = {
        "total": total, "passed": passed, "failed": failed,
        "quarantined": quarantined,
        "pass_rate_pct": round(passed / total * 100, 2) if total else 0,
    }
    logger.info("simulator_stopped", **summary)
    return summary


if __name__ == "__main__":
    run_simulator(interval_seconds=3.0, max_runs=10)