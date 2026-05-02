# coding: utf-8
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    record: dict[str, Any]
    passed: bool
    failed_rules: list[str] = field(default_factory=list)
    completeness_score: float = 0.0
    quarantine: bool = False

    @property
    def rejection_reason(self) -> str:
        return "; ".join(self.failed_rules)


def rule_run_id_present(record: dict) -> tuple[bool, str]:
    val = record.get("run_id", "")
    if not val or not str(val).strip():
        return False, "run_id is null or empty"
    return True, ""


def rule_run_id_format(record: dict) -> tuple[bool, str]:
    val = str(record.get("run_id", ""))
    if not val.startswith("RUN-"):
        return False, f"run_id '{val}' does not match RUN- format"
    return True, ""


def rule_sample_id_present(record: dict) -> tuple[bool, str]:
    val = record.get("sample_id", "")
    if not val or not str(val).strip():
        return False, "sample_id is null or empty"
    return True, ""


def rule_status_valid(record: dict) -> tuple[bool, str]:
    valid = {"PASSED", "FAILED", "QUARANTINED"}
    val = record.get("status", "")
    if val not in valid:
        return False, f"status '{val}' is not valid"
    return True, ""


def rule_mean_quality_non_negative(record: dict) -> tuple[bool, str]:
    val = record.get("mean_quality")
    if val is None:
        return True, ""
    try:
        if float(val) < 0:
            return False, f"mean_quality '{val}' is negative"
        return True, ""
    except (ValueError, TypeError):
        return False, f"mean_quality '{val}' is not a valid number"


def rule_coverage_depth_non_negative(record: dict) -> tuple[bool, str]:
    val = record.get("coverage_depth")
    if val is None:
        return True, ""
    try:
        if float(val) < 0:
            return False, f"coverage_depth '{val}' is negative"
        return True, ""
    except (ValueError, TypeError):
        return False, f"coverage_depth '{val}' is not a valid number"


def rule_organism_present(record: dict) -> tuple[bool, str]:
    val = record.get("organism", "")
    if not val or not str(val).strip():
        return False, "organism is missing"
    return True, ""


def rule_platform_present(record: dict) -> tuple[bool, str]:
    val = record.get("platform", "")
    if not val or not str(val).strip():
        return False, "platform is missing"
    return True, ""


def rule_total_bases_positive(record: dict) -> tuple[bool, str]:
    val = record.get("total_bases")
    if val is None:
        return True, ""
    try:
        if int(val) <= 0:
            return False, f"total_bases '{val}' must be positive"
        return True, ""
    except (ValueError, TypeError):
        return False, f"total_bases '{val}' is not a valid integer"


BLOCKING_RULES = [
    rule_run_id_present,
    rule_run_id_format,
    rule_sample_id_present,
    rule_status_valid,
]
WARNING_RULES = [
    rule_mean_quality_non_negative,
    rule_coverage_depth_non_negative,
    rule_organism_present,
    rule_platform_present,
    rule_total_bases_positive,
]
ALL_RULES = BLOCKING_RULES + WARNING_RULES


def _completeness(record: dict) -> float:
    fields = [
        "run_id", "sample_id", "patient_id", "organism", "platform",
        "library_strategy", "total_bases", "total_reads",
        "mean_quality", "coverage_depth", "run_timestamp",
    ]
    present = sum(1 for f in fields if record.get(f) not in (None, "", "null"))
    return round(present / len(fields), 4)


def validate_record(record: dict) -> ValidationResult:
    blocking_failures = []
    warning_failures  = []

    for rule in BLOCKING_RULES:
        passed, reason = rule(record)
        if not passed:
            blocking_failures.append(reason)

    for rule in WARNING_RULES:
        passed, reason = rule(record)
        if not passed:
            warning_failures.append(reason)

    quarantine   = len(blocking_failures) > 0
    completeness = _completeness(record)

    return ValidationResult(
        record=record,
        passed=not quarantine,
        failed_rules=blocking_failures + warning_failures,
        completeness_score=completeness,
        quarantine=quarantine,
    )