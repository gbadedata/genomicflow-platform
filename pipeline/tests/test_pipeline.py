# coding: utf-8
"""
Unit tests for message handling: every message must end processed, rejected
(stored with its reason) or retried, and only a stored outcome is acked.
"""
import json
from types import SimpleNamespace

import pytest

from pipeline.src.pipeline import ACK_OUTCOMES, Outcome, handle_message


def good_record(**overrides):
    record = {
        "run_id":           "RUN-ABCDEF123456",
        "sample_id":        "SAMP-12345678",
        "patient_id":       "PAT-AB1234",
        "organism":         "Homo sapiens",
        "platform":         "Illumina NovaSeq 6000",
        "library_strategy": "WGS",
        "total_bases":      150000000000,
        "total_reads":      1000000000,
        "mean_quality":     35.5,
        "coverage_depth":   50.0,
        "status":           "PASSED",
        "run_timestamp":    "2026-05-02T18:00:00Z",
        "variants":         [{"variant_id": "VAR-1", "sample_id": "SAMP-12345678"}],
        "quality_metrics":  [{"metric_id": "QM-1", "run_id": "RUN-ABCDEF123456",
                              "metric_name": "Q30", "metric_value": 92.0, "passed": True}],
    }
    record.update(overrides)
    return record


def received(body, message_id="msg-1", attempt=1):
    data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    return SimpleNamespace(
        ack_id="ack-1",
        delivery_attempt=attempt,
        message=SimpleNamespace(data=data, message_id=message_id),
    )


class FakeWriter:
    """Records calls; each write method's result can be set per test."""

    def __init__(self, run=True, variants=True, metrics=True, rejected=True, raise_on_run=False):
        self.results = {"run": run, "variants": variants, "metrics": metrics, "rejected": rejected}
        self.raise_on_run = raise_on_run
        self.calls = []

    def write_run(self, record, completeness):
        self.calls.append(("run", record["run_id"]))
        if self.raise_on_run:
            raise ConnectionError("BigQuery unavailable")
        return self.results["run"]

    def write_variants(self, variants, run_id):
        self.calls.append(("variants", run_id))
        return self.results["variants"]

    def write_quality_metrics(self, metrics, run_id):
        self.calls.append(("metrics", run_id))
        return self.results["metrics"]

    def write_rejected(self, message_id, rejection_type, reason, payload,
                       run_id=None, delivery_attempt=None):
        self.calls.append(("rejected", rejection_type, reason, payload, run_id, delivery_attempt))
        return self.results["rejected"]


class TestProcessed:

    def test_valid_record_writes_all_three_tables(self):
        writer = FakeWriter()
        assert handle_message(received(good_record()), writer) is Outcome.PROCESSED
        assert [c[0] for c in writer.calls] == ["run", "variants", "metrics"]

    def test_warning_rules_do_not_block(self):
        writer = FakeWriter()
        outcome = handle_message(received(good_record(organism=None)), writer)
        assert outcome is Outcome.PROCESSED

    def test_processed_is_acked(self):
        assert Outcome.PROCESSED in ACK_OUTCOMES


class TestRejected:

    def test_blocking_failure_is_stored_with_reason_and_payload(self):
        writer = FakeWriter()
        body = good_record(run_id="BAD-ID")
        outcome = handle_message(received(body, attempt=2), writer)
        assert outcome is Outcome.REJECTED
        kind, rtype, reason, payload, run_id, attempt = writer.calls[0]
        assert (kind, rtype, run_id, attempt) == ("rejected", "VALIDATION", "BAD-ID", 2)
        assert "does not match RUN- format" in reason
        assert json.loads(payload) == body

    def test_rejected_record_never_reaches_the_warehouse(self):
        writer = FakeWriter()
        handle_message(received(good_record(status="NOT-A-STATUS")), writer)
        assert all(c[0] == "rejected" for c in writer.calls)

    def test_unparseable_payload_is_stored(self):
        writer = FakeWriter()
        outcome = handle_message(received(b"{not json"), writer)
        assert outcome is Outcome.REJECTED
        assert writer.calls[0][1] == "UNPARSEABLE"
        assert writer.calls[0][3] == "{not json"

    @pytest.mark.parametrize("body", [b"[1, 2, 3]", b'"a string"', b"42"])
    def test_json_that_is_not_an_object_is_stored(self, body):
        writer = FakeWriter()
        assert handle_message(received(body), writer) is Outcome.REJECTED
        assert writer.calls[0][1] == "UNPARSEABLE"

    def test_rejected_is_acked(self):
        assert Outcome.REJECTED in ACK_OUTCOMES


class TestRetry:

    @pytest.mark.parametrize("failing", ["run", "variants", "metrics"])
    def test_any_failed_write_means_retry(self, failing):
        writer = FakeWriter(**{failing: False})
        assert handle_message(received(good_record()), writer) is Outcome.RETRY

    def test_failed_run_write_skips_child_writes(self):
        writer = FakeWriter(run=False)
        handle_message(received(good_record()), writer)
        assert [c[0] for c in writer.calls] == ["run"]

    def test_write_exception_means_retry(self):
        writer = FakeWriter(raise_on_run=True)
        assert handle_message(received(good_record()), writer) is Outcome.RETRY

    def test_failed_rejection_write_means_retry(self):
        writer = FakeWriter(rejected=False)
        outcome = handle_message(received(good_record(sample_id="")), writer)
        assert outcome is Outcome.RETRY

    def test_retry_is_not_acked(self):
        assert Outcome.RETRY not in ACK_OUTCOMES


class TestDryRun:

    def test_dry_run_writes_nothing(self):
        writer = FakeWriter()
        for body in (good_record(), good_record(run_id="BAD"), b"{not json"):
            assert handle_message(received(body), writer, dry_run=True) is Outcome.DRY_RUN
        assert writer.calls == []


class FakeSubscriber:
    """Serves one batch of messages, then an empty pull; records acks and nacks."""

    def __init__(self, batch):
        self.batches = [batch, []]
        self.acked, self.nacked = [], []

    def pull(self, request, timeout):
        return SimpleNamespace(received_messages=self.batches.pop(0) if self.batches else [])

    def acknowledge(self, request):
        self.acked.extend(request["ack_ids"])

    def modify_ack_deadline(self, request):
        assert request["ack_deadline_seconds"] == 0
        self.nacked.extend(request["ack_ids"])


class TestRunPipelineLoop:

    def _run(self, monkeypatch, batch, writer):
        import pipeline.src.pipeline as pl
        sub = FakeSubscriber(batch)
        monkeypatch.setattr(pl.pubsub_v1, "SubscriberClient", lambda: sub)
        monkeypatch.setattr(pl, "BigQueryWriter", lambda: writer)
        return pl.run_pipeline(max_messages=100), sub

    def _msg(self, body, ack_id):
        m = received(body, message_id=f"m-{ack_id}")
        m.ack_id = ack_id
        return m

    def test_acks_stored_outcomes_and_nacks_failures(self, monkeypatch):
        class PoisonAwareWriter(FakeWriter):
            def write_run(self, record, completeness):
                self.calls.append(("run", record["run_id"]))
                return record.get("total_bases") != "lots"

        batch = [
            self._msg(good_record(), "a-good"),
            self._msg(good_record(run_id="BAD-1"), "a-bad"),
            self._msg(b"not json", "a-junk"),
            self._msg(good_record(run_id="RUN-POISON", total_bases="lots"), "a-poison"),
        ]
        summary, sub = self._run(monkeypatch, batch, PoisonAwareWriter())
        assert summary == {"total": 4, "processed": 1, "rejected": 2, "retry": 1, "dry_run": 0}
        assert sorted(sub.acked) == ["a-bad", "a-good", "a-junk"]
        assert sub.nacked == ["a-poison"]

    def test_stops_when_no_messages(self, monkeypatch):
        summary, sub = self._run(monkeypatch, [], FakeWriter())
        assert summary["total"] == 0 and sub.acked == [] and sub.nacked == []


class TestListenMode:
    """run_seconds > 0 keeps pulling through empty pulls until the time is up."""

    def test_keeps_listening_through_empty_pulls_and_timeouts(self, monkeypatch):
        import pipeline.src.pipeline as pl

        clock = iter(range(1000))
        monkeypatch.setattr(pl.time, "monotonic", lambda: next(clock))
        monkeypatch.setattr(pl.time, "sleep", lambda s: None)

        class Sub(FakeSubscriber):
            def __init__(self):
                super().__init__([])
                self.responses = [
                    [],                                        # empty pull
                    pl.gexc.DeadlineExceeded("no messages"),   # pull timed out
                    [received(good_record())],                 # message arrives later
                ]

            def pull(self, request, timeout):
                item = self.responses.pop(0) if self.responses else []
                if isinstance(item, Exception):
                    raise item
                return SimpleNamespace(received_messages=item)

        sub = Sub()
        monkeypatch.setattr(pl.pubsub_v1, "SubscriberClient", lambda: sub)
        monkeypatch.setattr(pl, "BigQueryWriter", lambda: FakeWriter())
        summary = pl.run_pipeline(run_seconds=10)
        assert summary["processed"] == 1
        assert sub.acked == ["ack-1"]

    def test_drain_mode_still_stops_at_first_empty_pull(self, monkeypatch):
        import pipeline.src.pipeline as pl
        sub = FakeSubscriber([])
        sub.batches = [[], [received(good_record())]]
        monkeypatch.setattr(pl.pubsub_v1, "SubscriberClient", lambda: sub)
        monkeypatch.setattr(pl, "BigQueryWriter", lambda: FakeWriter())
        assert pl.run_pipeline()["total"] == 0
