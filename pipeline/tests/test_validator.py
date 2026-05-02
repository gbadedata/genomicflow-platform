# coding: utf-8
"""Unit tests for the pipeline validator."""
import pytest
from pipeline.src.validator import (
    validate_record, rule_run_id_present, rule_run_id_format,
    rule_status_valid, rule_mean_quality_non_negative,
)


def good_record():
    return {
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
    }


class TestRules:

    def test_run_id_present_passes(self):
        passed, _ = rule_run_id_present({"run_id": "RUN-ABC123"})
        assert passed is True

    def test_run_id_present_fails_empty(self):
        passed, reason = rule_run_id_present({"run_id": ""})
        assert passed is False
        assert "null" in reason

    def test_run_id_format_passes(self):
        passed, _ = rule_run_id_format({"run_id": "RUN-ABCDEF123456"})
        assert passed is True

    def test_run_id_format_fails(self):
        passed, reason = rule_run_id_format({"run_id": "INVALID-123"})
        assert passed is False

    def test_status_valid_passes(self):
        for status in ["PASSED", "FAILED", "QUARANTINED"]:
            passed, _ = rule_status_valid({"status": status})
            assert passed is True

    def test_status_invalid_fails(self):
        passed, reason = rule_status_valid({"status": "UNKNOWN"})
        assert passed is False

    def test_quality_non_negative_passes(self):
        passed, _ = rule_mean_quality_non_negative({"mean_quality": 35.0})
        assert passed is True

    def test_quality_negative_fails(self):
        passed, reason = rule_mean_quality_non_negative({"mean_quality": -1.0})
        assert passed is False


class TestValidateRecord:

    def test_good_record_passes(self):
        result = validate_record(good_record())
        assert result.passed is True
        assert result.quarantine is False
        assert result.completeness_score > 0.8

    def test_missing_run_id_quarantines(self):
        rec = good_record()
        rec["run_id"] = ""
        result = validate_record(rec)
        assert result.quarantine is True

    def test_invalid_run_id_format_quarantines(self):
        rec = good_record()
        rec["run_id"] = "INVALID-123"
        result = validate_record(rec)
        assert result.quarantine is True

    def test_invalid_status_quarantines(self):
        rec = good_record()
        rec["status"] = "UNKNOWN"
        result = validate_record(rec)
        assert result.quarantine is True

    def test_completeness_score_computed(self):
        result = validate_record(good_record())
        assert 0.0 < result.completeness_score <= 1.0

    def test_missing_optional_fields_lowers_completeness(self):
        rec = good_record()
        rec["patient_id"]     = None
        rec["coverage_depth"] = None
        result = validate_record(rec)
        assert result.completeness_score < 1.0