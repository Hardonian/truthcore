"""Tests for the provenance module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from truthcore.provenance.manifest import EvidenceManifest, ManifestEntry
from truthcore.provenance.signing import Signer, Signature, SigningError
from truthcore.provenance.verifier import BundleVerifier, VerificationResult
from truthcore.security import SecurityLimits, SecurityError

# Check if cryptography is available for signature tests
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


class TestManifestEntry:
    """Test the ManifestEntry class."""

    def test_entry_creation(self):
        """Test creating an entry."""
        entry = ManifestEntry(
            path="test/file.txt",
            sha256="abc123",
            size=100,
            content_type="text/plain",
        )
        assert entry.path == "test/file.txt"
        assert entry.sha256 == "abc123"
        assert entry.size == 100

    def test_entry_from_file(self, tmp_path: Path):
        """Test creating entry from file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        entry = ManifestEntry.from_file(test_file, tmp_path)

        assert entry.path == "test.txt"
        assert entry.size == 13
        assert len(entry.sha256) == 64  # SHA-256 hex


class TestEvidenceManifest:
    """Test the EvidenceManifest class."""

    def test_manifest_creation(self):
        """Test creating a manifest."""
        manifest = EvidenceManifest(
            run_manifest_hash="abc123",
            config_hash="def456",
        )
        assert manifest.run_manifest_hash == "abc123"
        assert manifest.config_hash == "def456"

    def test_add_entry(self):
        """Test adding entries."""
        manifest = EvidenceManifest()
        entry = ManifestEntry(path="test.txt", sha256="abc123", size=100)
        manifest.add_entry(entry)
        assert len(manifest.entries) == 1

    def test_compute_hash(self):
        """Test computing manifest hash."""
        manifest = EvidenceManifest()
        entry = ManifestEntry(path="test.txt", sha256="abc123", size=100)
        manifest.add_entry(entry)

        hash1 = manifest.compute_manifest_hash()
        hash2 = manifest.compute_manifest_hash()

        assert hash1 == hash2  # Deterministic
        assert len(hash1) == 64  # SHA-256 hex

    def test_roundtrip_dict(self):
        """Test roundtrip through dict."""
        manifest = EvidenceManifest(
            run_manifest_hash="abc123",
            config_hash="def456",
        )
        entry = ManifestEntry(path="test.txt", sha256="abc123", size=100)
        manifest.add_entry(entry)

        data = manifest.to_dict()
        manifest2 = EvidenceManifest.from_dict(data)

        assert manifest2.run_manifest_hash == "abc123"
        assert len(manifest2.entries) == 1

    def test_generate_from_directory(self, tmp_path: Path):
        """Test generating manifest from directory."""
        # Create test files
        (tmp_path / "file1.txt").write_text("Hello")
        (tmp_path / "file2.json").write_text('{"key": "value"}')

        manifest = EvidenceManifest.generate(tmp_path)

        assert len(manifest.entries) == 2
        assert manifest.compute_manifest_hash() is not None

    def test_security_limits(self, tmp_path: Path):
        """Test security limits skip oversized files."""
        # Create a large file
        large_file = tmp_path / "large.bin"
        large_file.write_bytes(b"0" * (200 * 1024 * 1024))  # 200MB

        # Create a normal file
        (tmp_path / "normal.txt").write_text("small content")

        limits = SecurityLimits(max_file_size=100 * 1024 * 1024)  # 100MB limit

        # Generate manifest - should skip oversized file without raising error
        manifest = EvidenceManifest.generate(tmp_path, limits=limits)

        # Should only have the normal file, not the large one
        assert len(manifest.entries) == 1
        assert manifest.entries[0].path == "normal.txt"

    def test_max_files_limit(self, tmp_path: Path):
        """Test max files limit."""
        # Create many files
        for i in range(15000):
            (tmp_path / f"file{i}.txt").write_text("x")

        with pytest.raises(SecurityError):
            EvidenceManifest.generate(tmp_path, max_files=10000)


class TestSigner:
    """Test the Signer class."""

    def test_generate_keys(self):
        """Test key generation."""
        private_key, public_key = Signer.generate_keys()

        assert len(private_key) == 32
        assert len(public_key) == 32

    def test_keys_to_env_format(self):
        """Test converting keys to env format."""
        private_key = b"x" * 32
        public_key = b"y" * 32

        priv_b64, pub_b64 = Signer.keys_to_env_format(private_key, public_key)

        assert isinstance(priv_b64, str)
        assert isinstance(pub_b64, str)
        assert len(priv_b64) > 0

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography library not installed")
    def test_sign_and_verify(self):
        """Test signing and verifying."""
        private_key, public_key = Signer.generate_keys()

        signer = Signer(private_key=private_key, public_key=public_key)
        assert signer.is_configured() is True

        message = b"Hello, World!"
        signature = signer.sign(message, "test comment")

        assert signature.signature is not None
        assert signature.public_key == public_key

        # Verify
        is_valid = signer.verify(message, signature)
        assert is_valid is True

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography library not installed")
    def test_verify_wrong_message(self):
        """Test verification fails with wrong message."""
        private_key, public_key = Signer.generate_keys()

        signer = Signer(private_key=private_key, public_key=public_key)
        signature = signer.sign(b"original message")

        # Try to verify with different message
        is_valid = signer.verify(b"different message", signature)
        assert is_valid is False

    def test_signature_roundtrip_bytes(self):
        """Test signature serialization."""
        private_key, public_key = Signer.generate_keys()

        signer = Signer(private_key=private_key, public_key=public_key)
        signature = signer.sign(b"test")

        sig_bytes = signature.to_bytes()
        signature2 = Signature.from_bytes(sig_bytes)

        assert signature2.signature == signature.signature

    def test_unconfigured_signer(self):
        """Test that unconfigured signer raises error."""
        signer = Signer()
        assert signer.is_configured() is False

        with pytest.raises(SigningError):
            signer.sign(b"test")


class TestBundleVerifier:
    """Test the BundleVerifier."""

    def test_verify_valid_bundle(self, tmp_path: Path):
        """Test verifying a valid bundle."""
        # Create bundle
        bundle_dir = tmp_path / "bundle"
        bundle_dir.mkdir()

        # Create files
        (bundle_dir / "data.json").write_text('{"key": "value"}')
        (bundle_dir / "report.txt").write_text("Test report")

        # Generate manifest
        manifest = EvidenceManifest.generate(bundle_dir)
        manifest.write_json(bundle_dir / "evidence.manifest.json")

        # Verify
        verifier = BundleVerifier()
        result = verifier.verify(bundle_dir)

        assert result.valid is True
        assert result.manifest_valid is True
        assert result.files_checked == 2
        assert result.files_valid == 2
        assert len(result.files_tampered) == 0

    def test_detect_tampering(self, tmp_path: Path):
        """Test detecting tampered files."""
        # Create bundle
        bundle_dir = tmp_path / "bundle"
        bundle_dir.mkdir()

        # Create file
        data_file = bundle_dir / "data.json"
        data_file.write_text('{"key": "value"}')

        # Generate manifest
        manifest = EvidenceManifest.generate(bundle_dir)
        manifest.write_json(bundle_dir / "evidence.manifest.json")

        # Tamper with file
        data_file.write_text('{"key": "tampered"}')

        # Verify
        verifier = BundleVerifier()
        result = verifier.verify(bundle_dir)

        assert result.valid is False
        assert len(result.files_tampered) == 1

    def test_detect_missing_files(self, tmp_path: Path):
        """Test detecting missing files."""
        # Create bundle
        bundle_dir = tmp_path / "bundle"
        bundle_dir.mkdir()

        # Create file
        (bundle_dir / "data.json").write_text('{"key": "value"}')

        # Generate manifest
        manifest = EvidenceManifest.generate(bundle_dir)
        manifest.write_json(bundle_dir / "evidence.manifest.json")

        # Delete file
        (bundle_dir / "data.json").unlink()

        # Verify
        verifier = BundleVerifier()
        result = verifier.verify(bundle_dir)

        assert result.valid is False
        assert len(result.files_missing) == 1

    def test_detect_added_files(self, tmp_path: Path):
        """Test detecting added files."""
        # Create bundle
        bundle_dir = tmp_path / "bundle"
        bundle_dir.mkdir()

        # Create file
        (bundle_dir / "data.json").write_text('{"key": "value"}')

        # Generate manifest
        manifest = EvidenceManifest.generate(bundle_dir)
        manifest.write_json(bundle_dir / "evidence.manifest.json")

        # Add new file
        (bundle_dir / "extra.txt").write_text("Extra file")

        # Verify
        verifier = BundleVerifier()
        result = verifier.verify(bundle_dir)

        # Bundle is still valid, but we note the added files
        assert len(result.files_added) == 1
        assert "extra.txt" in result.files_added

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography library not installed")
    def test_verify_with_signature(self, tmp_path: Path):
        """Test verifying with signature."""
        # Create keys
        private_key, public_key = Signer.generate_keys()

        # Create bundle
        bundle_dir = tmp_path / "bundle"
        bundle_dir.mkdir()
        (bundle_dir / "data.json").write_text('{"key": "value"}')

        # Generate and sign manifest
        manifest = EvidenceManifest.generate(bundle_dir)
        manifest.write_json(bundle_dir / "evidence.manifest.json")

        signer = Signer(private_key=private_key, public_key=public_key)
        signer.sign_file(bundle_dir / "evidence.manifest.json", bundle_dir / "evidence.sig")

        # Verify
        verifier = BundleVerifier(public_key=public_key)
        result = verifier.verify(bundle_dir)

        assert result.valid is True
        assert result.signature_valid is True

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography library not installed")
    def test_signature_tampering(self, tmp_path: Path):
        """Test detecting signature tampering."""
        # Create keys
        private_key, public_key = Signer.generate_keys()

        # Create bundle
        bundle_dir = tmp_path / "bundle"
        bundle_dir.mkdir()
        (bundle_dir / "data.json").write_text('{"key": "value"}')

        # Generate and sign manifest
        manifest = EvidenceManifest.generate(bundle_dir)
        manifest.write_json(bundle_dir / "evidence.manifest.json")

        signer = Signer(private_key=private_key, public_key=public_key)
        signer.sign_file(bundle_dir / "evidence.manifest.json", bundle_dir / "evidence.sig")

        # Tamper with manifest
        (bundle_dir / "evidence.manifest.json").write_text('{"tampered": true}')

        # Verify
        verifier = BundleVerifier(public_key=public_key)
        result = verifier.verify(bundle_dir)

        assert result.signature_valid is False


class TestVerificationResult:
    """Test the VerificationResult class."""

    def test_result_creation(self):
        """Test creating a result."""
        result = VerificationResult(valid=True, manifest_valid=True)
        assert result.valid is True
        assert result.manifest_valid is True

    def test_result_to_dict(self):
        """Test converting to dict."""
        result = VerificationResult(valid=True, manifest_valid=True)
        result.files_checked = 10
        result.files_valid = 10

        data = result.to_dict()
        assert data["valid"] is True
        assert data["files_checked"] == 10

    def test_markdown_output(self, tmp_path: Path):
        """Test markdown report generation."""
        result = VerificationResult(valid=False, manifest_valid=True)
        result.files_tampered = [
            {"path": "file.txt", "expected_hash": "abc", "actual_hash": "def"}
        ]

        md_path = tmp_path / "report.md"
        result.write_markdown(md_path)

        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "INVALID" in content
        assert "file.txt" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
