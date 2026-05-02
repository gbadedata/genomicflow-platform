# coding: utf-8
"""Unit tests for the genomic data generator."""
import pytest
from simulator.src.generator import generate_run, _compute_completeness
from simulator.src.models import RunStatus, SequencingPlatform, LibraryStrategy


class TestGenerateRun:

    def test_generates_valid_run(self):
        run = generate_run()
        assert run.run_id.startswith("RUN-")
        assert run.sample_id.startswith("SAMP-")
        assert run.organism in ["Homo sapiens", "Mus musculus", "Rattus norvegicus"]
        assert run.status in list(RunStatus)

    def test_completeness_score_between_0_and_1(self):
        run = generate_run()
        assert 0.0 <= run.completeness_score <= 1.0

    def test_generates_variants(self):
        run = generate_run()
        assert len(run.variants) >= 3
        for v in run.variants:
            assert v.run_id == run.run_id
            assert v.chromosome in [str(i) for i in range(1, 23)] + ["X", "Y", "MT"]

    def test_generates_quality_metrics(self):
        run = generate_run()
        assert len(run.quality_metrics) == 7
        metric_names = [m.metric_name for m in run.quality_metrics]
        assert "mean_base_quality" in metric_names
        assert "coverage_depth" in metric_names

    def test_force_fail_produces_failed_run(self):
        run = generate_run(force_fail=True)
        assert run.status == RunStatus.FAILED
        assert run.failure_reason is not None

    def test_force_quarantine_produces_quarantined_run(self):
        run = generate_run(force_quarantine=True)
        assert run.status == RunStatus.QUARANTINED
        assert run.failure_reason is not None

    def test_specific_platform(self):
        run = generate_run(platform=SequencingPlatform.OXFORD_NANOPORE)
        assert run.platform == SequencingPlatform.OXFORD_NANOPORE

    def test_specific_strategy(self):
        run = generate_run(strategy=LibraryStrategy.RNA_SEQ)
        assert run.library_strategy == LibraryStrategy.RNA_SEQ

    def test_failed_run_has_degraded_metrics(self):
        run = generate_run(force_fail=True)
        assert run.mean_quality < 26.0
        assert run.coverage_depth < 16.0

    def test_passed_run_has_good_metrics(self):
        passed_runs = [generate_run() for _ in range(20)]
        passed = [r for r in passed_runs if r.status == RunStatus.PASSED]
        if passed:
            for r in passed:
                # Quality threshold varies by platform
                # Oxford Nanopore legitimately scores 12-20
                assert r.mean_quality >= 10.0