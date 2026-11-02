"""Claim schema, validation, and writer for CLAIM_TABLE.substrate.json."""

from .schema import (
    Claim,
    ClaimRejected,
    PredictionType,
    is_falsifiable,
    validate_claim,
)
from .table import ClaimTable
from .writer import ClaimWriter
from .noise_precursor import build_noise_precursor_claim, locate_noise_row

__all__ = [
    "Claim",
    "ClaimRejected",
    "ClaimTable",
    "ClaimWriter",
    "build_noise_precursor_claim",
    "locate_noise_row",
    "PredictionType",
    "is_falsifiable",
    "validate_claim",
]
