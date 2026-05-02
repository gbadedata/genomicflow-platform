# coding: utf-8
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SequencingPlatform(str, Enum):
    ILLUMINA_NOVASEQ = "Illumina NovaSeq 6000"
    ILLUMINA_NEXTSEQ = "Illumina NextSeq 2000"
    ILLUMINA_MISEQ   = "Illumina MiSeq"
    OXFORD_NANOPORE  = "Oxford Nanopore PromethION"
    PACBIO_SEQUEL    = "PacBio Sequel IIe"


class LibraryStrategy(str, Enum):
    WGS      = "WGS"
    WES      = "WES"
    RNA_SEQ  = "RNA-Seq"
    AMPLICON = "AMPLICON"
    TARGETED = "Targeted"


class RunStatus(str, Enum):
    PASSED      = "PASSED"
    FAILED      = "FAILED"
    QUARANTINED = "QUARANTINED"


class ClinicalSignificance(str, Enum):
    PATHOGENIC        = "PATHOGENIC"
    LIKELY_PATHOGENIC = "LIKELY_PATHOGENIC"
    UNCERTAIN         = "UNCERTAIN"
    LIKELY_BENIGN     = "LIKELY_BENIGN"
    BENIGN            = "BENIGN"


class VariantEvent(BaseModel):
    variant_id:            str = Field(default_factory=lambda: f"VAR-{uuid.uuid4().hex[:8].upper()}")
    run_id:                str
    sample_id:             str
    chromosome:            str
    position:              int
    reference_allele:      str
    alternate_allele:      str
    variant_type:          str
    quality_score:         float
    clinical_significance: ClinicalSignificance
    detected_at:           datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QualityMetricEvent(BaseModel):
    metric_id:    str = Field(default_factory=lambda: f"QM-{uuid.uuid4().hex[:8].upper()}")
    run_id:       str
    metric_name:  str
    metric_value: float
    threshold:    Optional[float] = None
    passed:       bool
    measured_at:  datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SequencingRunEvent(BaseModel):
    run_id:             str = Field(default_factory=lambda: f"RUN-{uuid.uuid4().hex[:12].upper()}")
    sample_id:          str = Field(default_factory=lambda: f"SAMP-{uuid.uuid4().hex[:8].upper()}")
    patient_id:         Optional[str] = None
    organism:           str = "Homo sapiens"
    platform:           SequencingPlatform = SequencingPlatform.ILLUMINA_NOVASEQ
    library_strategy:   LibraryStrategy = LibraryStrategy.WGS
    total_bases:        Optional[int] = None
    total_reads:        Optional[int] = None
    mean_quality:       Optional[float] = None
    coverage_depth:     Optional[float] = None
    status:             RunStatus = RunStatus.PASSED
    failure_reason:     Optional[str] = None
    run_timestamp:      datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ingested_at:        datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completeness_score: Optional[float] = None
    variants:           list[VariantEvent] = Field(default_factory=list)
    quality_metrics:    list[QualityMetricEvent] = Field(default_factory=list)