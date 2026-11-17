# coding: utf-8
"""Unit tests for the BigQuery writer, using a fake client (no GCP calls)."""
from pipeline.src.bq_writer import BigQueryWriter


class FakeClient:

    def __init__(self, errors=None):
        self.errors = errors or []
        self.calls = []

    def insert_rows_json(self, table, rows, row_ids=None):
        self.calls.append({"table": table, "rows": rows, "row_ids": row_ids})
        return self.errors


def run_record():
    return {"run_id": "RUN-ABCDEF123456", "sample_id": "SAMP-1", "status": "PASSED"}


class TestInsertIds:

    def test_run_insert_id_is_the_run_id(self):
        client = FakeClient()
        assert BigQueryWriter(client).write_run(run_record(), 0.9) is True
        assert client.calls[0]["row_ids"] == ["RUN-ABCDEF123456"]

    def test_child_insert_ids_are_stable_across_redelivery(self):
        variants = [{"variant_id": "VAR-1"}, {"variant_id": "VAR-2"}]
        first, second = FakeClient(), FakeClient()
        BigQueryWriter(first).write_variants(variants, "RUN-X")
        BigQueryWriter(second).write_variants(variants, "RUN-X")
        assert first.calls[0]["row_ids"] == second.calls[0]["row_ids"]
        assert first.calls[0]["row_ids"] == ["RUN-X:variant:VAR-1", "RUN-X:variant:VAR-2"]

    def test_metric_without_id_falls_back_to_position(self):
        client = FakeClient()
        BigQueryWriter(client).write_quality_metrics([{"metric_name": "Q30"}], "RUN-X")
        assert client.calls[0]["row_ids"] == ["RUN-X:metric:0"]
        assert client.calls[0]["rows"][0]["run_id"] == "RUN-X"

    def test_rejected_insert_id_is_the_message_id(self):
        client = FakeClient()
        ok = BigQueryWriter(client).write_rejected("m-9", "VALIDATION", "bad", "{}", "RUN-X", 3)
        assert ok is True
        call = client.calls[0]
        assert call["row_ids"] == ["rejected:m-9"]
        row = call["rows"][0]
        assert (row["rejection_type"], row["rejection_reason"], row["delivery_attempt"]) == (
            "VALIDATION", "bad", 3)


class TestResults:

    def test_insert_errors_return_false(self):
        writer = BigQueryWriter(FakeClient(errors=[{"index": 0, "errors": ["boom"]}]))
        assert writer.write_run(run_record(), 0.9) is False
        assert writer.write_variants([{"variant_id": "V"}], "RUN-X") is False
        assert writer.write_rejected("m", "UNPARSEABLE", "bad", "x") is False

    def test_empty_lists_are_a_success_without_a_call(self):
        client = FakeClient()
        writer = BigQueryWriter(client)
        assert writer.write_variants([], "RUN-X") is True
        assert writer.write_quality_metrics([], "RUN-X") is True
        assert client.calls == []
