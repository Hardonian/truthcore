"""Evidence Signing + Provenance (tamper-evident bundles).

Provides deterministic evidence manifest generation and optional
cryptographic signing for tamper detection.
"""

from __future__ import annotations

from truthcore.provenance.manifest import EvidenceManifest, ManifestEntry
from truthcore.provenance.signing import Signer, SigningError, VerificationError
from truthcore.provenance.verifier import BundleVerifier

__all__ = [
    "EvidenceManifest",
    "ManifestEntry",
    "Signer",
    "SigningError",
    "VerificationError",
    "BundleVerifier",
]
