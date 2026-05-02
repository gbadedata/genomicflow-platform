# coding: utf-8
import random
import uuid
from datetime import datetime, timezone
from typing import Optional
import structlog
from faker import Faker
from simulator.src.models import (
    ClinicalSignificance, LibraryStrategy, QualityMetricEvent,
    RunStatus, SequencingPlatform, SequencingRunEvent, VariantEvent,
)

logger = structlog.get_logger(__name__)
fake = Faker()

PLATFORM_CONFIGS = {
    SequencingPlatform.ILLUMINA_NOVASEQ: {
        "bases_range":    (80_000_000_000, 200_000_000_000),
        "reads_range":    (500_000_000, 1_500_000_000),
        "quality_range":  (30.0, 38.0),
        "coverage_range": (30.0, 100.0),
    },
    SequencingPlatform.ILLUMINA_NEXTSEQ: {
        "bases_range":    (40_000_000_000, 120_000_000_000),
        "reads_range":    (200_000_000, 800_000_000),
        "quality_range":  (28.0, 36.0),
        "coverage_range": (20.0, 80.0),
    },
    SequencingPlatform.ILLUMINA_MISEQ: {
        "bases_range":    (1_000_000_000, 15_000_000_000),
        "reads_range":    (5_000_000, 25_000_000),
        "quality_range":  (25.0, 35.0),
        "coverage_range": (10.0, 50.0),
    },
    SequencingPlatform.OXFORD_NANOPORE: {
        "bases_range":    (10_000_000_000, 50_000_000_000),
        "reads_range":    (2_000_000, 10_000_000),
        "quality_range":  (12.0, 20.0),
        "coverage_range": (20.0, 60.0),
    },
    SequencingPlatform.PACBIO_SEQUEL: {
        "bases_range":    (5_000_000_000, 30_000_000_000),
        "reads_range":    (1_000_000, 5_000_000),
        "quality_range":  (20.0, 30.0),
        "coverage_range": (15.0, 50.0),
    },
}

CHROMOSOMES = [str(i) for i in range(1, 23)] + ["X", "Y", "MT"]
VARIANT_TYPES = ["SNV", "INDEL", "CNV", "SV", "MNV"]
ORGANISMS = ["Homo sapiens"] * 8 + ["Mus musculus"] + ["Rattus norvegicus"]


def _generate_variants(run_id: str, sample_id: str, count: int = 5) -> list[VariantEvent]:
    variants = []
    for _ in range(count):
        ref = random.choice(["A", "T", "G", "C"])
        alt = random.choice([b for b in ["A", "T", "G", "C"] if b != ref])
        variants.append(VariantEvent(
            run_id=run_id,
            sample_id=sample_id,
            chromosome=random.choice(CHROMOSOMES),
            position=random.randint(1, 248_956_422),
            reference_allele=ref,
            alternate_allele=alt,
            variant_type=random.choice(VARIANT_TYPES),
            quality_score=round(random.uniform(20.0, 60.0), 2),
            clinical_significance=random.choice(list(ClinicalSignificance)),
        ))
    return variants


def _generate_quality_metrics(run_id: str, mean_quality: float, coverage: float) -> list[QualityMetricEvent]:
    metrics = [
        ("mean_base_quality", mean_quality,                        30.0,  mean_quality >= 30.0),
        ("coverage_depth",    coverage,                            30.0,  coverage >= 30.0),
        ("q30_percentage",    round(random.uniform(70, 95), 2),    80.0,  True),
        ("duplicate_rate",    round(random.uniform(0.01, 0.15), 4), 0.20, True),
        ("mapping_rate",      round(random.uniform(0.85, 0.99), 4), 0.90, True),
        ("gc_content",        round(random.uniform(0.40, 0.60), 4), None, True),
        ("insert_size_median", round(random.uniform(150, 350), 1), None,  True),
    ]
    return [
        QualityMetricEvent(
            run_id=run_id,
            metric_name=name,
            metric_value=value,
            threshold=threshold,
            passed=passed,
        )
        for name, value, threshold, passed in metrics
    ]


def _compute_completeness(run: SequencingRunEvent) -> float:
    fields = [
        run.sample_id, run.patient_id, run.organism,
        run.platform, run.library_strategy,
        run.total_bases, run.total_reads,
        run.mean_quality, run.coverage_depth,
        run.run_timestamp,
    ]
    present = sum(1 for f in fields if f is not None and f != "")
    return round(present / len(fields), 4)


def generate_run(
    platform: Optional[SequencingPlatform] = None,
    strategy: Optional[LibraryStrategy] = None,
    force_fail: bool = False,
    force_quarantine: bool = False,
) -> SequencingRunEvent:
    platform = platform or random.choice(list(SequencingPlatform))
    strategy = strategy or random.choice(list(LibraryStrategy))
    config   = PLATFORM_CONFIGS[platform]

    run_id    = f"RUN-{uuid.uuid4().hex[:12].upper()}"
    sample_id = f"SAMP-{uuid.uuid4().hex[:8].upper()}"
    patient_id = f"PAT-{fake.bothify('??####').upper()}"

    total_bases    = random.randint(*config["bases_range"])
    total_reads    = random.randint(*config["reads_range"])
    mean_quality   = round(random.uniform(*config["quality_range"]), 2)
    coverage_depth = round(random.uniform(*config["coverage_range"]), 2)

    rand = random.random()
    if force_fail or rand < 0.05:
        status = RunStatus.FAILED
        failure_reason = random.choice([
            "Mean base quality below threshold (Q30 < 80%)",
            "Coverage depth insufficient (< 30x)",
            "Excessive duplicate rate (> 20%)",
            "Low mapping rate (< 90%)",
            "Sample contamination detected",
        ])
        mean_quality   = round(random.uniform(10.0, 25.0), 2)
        coverage_depth = round(random.uniform(1.0, 15.0), 2)
    elif force_quarantine or rand < 0.07:
        status = RunStatus.QUARANTINED
        failure_reason = random.choice([
            "Missing patient consent metadata",
            "Ambiguous sample ID - possible mislabelling",
            "Run date outside expected submission window",
        ])
    else:
        status = RunStatus.PASSED
        failure_reason = None

    variants        = _generate_variants(run_id, sample_id, count=random.randint(3, 12))
    quality_metrics = _generate_quality_metrics(run_id, mean_quality, coverage_depth)

    run = SequencingRunEvent(
        run_id=run_id,
        sample_id=sample_id,
        patient_id=patient_id,
        organism=random.choice(ORGANISMS),
        platform=platform,
        library_strategy=strategy,
        total_bases=total_bases,
        total_reads=total_reads,
        mean_quality=mean_quality,
        coverage_depth=coverage_depth,
        status=status,
        failure_reason=failure_reason,
        variants=variants,
        quality_metrics=quality_metrics,
    )
    run.completeness_score = _compute_completeness(run)

    logger.info(
        "run_generated",
        run_id=run_id,
        platform=platform.value,
        status=status.value,
        completeness=run.completeness_score,
    )
    return run