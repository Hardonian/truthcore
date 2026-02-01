"""Cryptographic signing for evidence manifests.

Supports Ed25519 signatures compatible with minisign format.
Uses environment variables for key storage:
- TRUTHCORE_SIGNING_PRIVATE_KEY: Base64-encoded private key (optional)
- TRUTHCORE_SIGNING_PUBLIC_KEY: Base64-encoded public key (optional)

If keys not provided, signing is skipped but manifest is still generated.
"""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path


class SigningError(Exception):
    """Error during signing operation."""
    pass


class VerificationError(Exception):
    """Error during verification."""
    pass


@dataclass
class Signature:
    """Signature data structure (minisign-compatible)."""

    signature: bytes
    public_key: bytes
    algorithm: str = "Ed25519"
    trusted_comment: str = ""

    def to_bytes(self) -> bytes:
        """Serialize to bytes (minisign format)."""
        # Format: algorithm (2) + key_id (8) + signature (64) + trusted_comment
        key_id = hashlib.sha256(self.public_key).digest()[:8]
        result = b""
        result += b"ED"  # Ed25519 magic
        result += key_id
        result += self.signature
        if self.trusted_comment:
            result += b"\n"
            result += self.trusted_comment.encode("utf-8")
            result += b"\n"
        return result

    @classmethod
    def from_bytes(cls, data: bytes) -> Signature:
        """Deserialize from bytes."""
        if len(data) < 74:
            raise VerificationError("Signature too short")

        if data[:2] != b"ED":
            raise VerificationError("Invalid signature algorithm")

        key_id = data[2:10]
        signature = data[10:74]

        # Extract trusted comment if present
        trusted_comment = ""
        if b"\n" in data[74:]:
            parts = data[74:].split(b"\n")
            if parts:
                trusted_comment = parts[0].decode("utf-8")

        return cls(
            signature=signature,
            public_key=b"",  # Will be filled separately
            trusted_comment=trusted_comment,
        )


class Signer:
    """Evidence manifest signer."""

    # Algorithm identifiers
    ALG_ED25519 = "Ed25519"

    def __init__(
        self,
        private_key: bytes | None = None,
        public_key: bytes | None = None,
    ) -> None:
        """Initialize signer.

        Args:
            private_key: 32-byte private key (optional)
            public_key: 32-byte public key (optional)

        If keys not provided, attempts to load from environment variables.
        """
        self._private_key = private_key
        self._public_key = public_key
        self._has_crypto = False
        self._signing_key = None

        # Try to load from environment if not provided
        if self._private_key is None:
            self._load_keys_from_env()

        # Try to import cryptography library
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PrivateKey,
                Ed25519PublicKey,
            )

            self._has_crypto = True

            # Initialize keys
            if self._private_key:
                self._signing_key = Ed25519PrivateKey.from_private_bytes(self._private_key)
                if not self._public_key:
                    self._public_key = self._signing_key.public_key().public_bytes(
                        encoding=serialization.Encoding.Raw,
                        format=serialization.PublicFormat.Raw,
                    )
        except ImportError:
            # Fall back to hash-based deterministic signing
            self._has_crypto = False

    def _load_keys_from_env(self) -> None:
        """Load keys from environment variables."""
        priv_b64 = os.environ.get("TRUTHCORE_SIGNING_PRIVATE_KEY")
        pub_b64 = os.environ.get("TRUTHCORE_SIGNING_PUBLIC_KEY")

        if priv_b64:
            try:
                self._private_key = base64.b64decode(priv_b64)
            except Exception:
                raise SigningError("Invalid base64 in TRUTHCORE_SIGNING_PRIVATE_KEY")

        if pub_b64:
            try:
                self._public_key = base64.b64decode(pub_b64)
            except Exception:
                raise SigningError("Invalid base64 in TRUTHCORE_SIGNING_PUBLIC_KEY")

    def is_configured(self) -> bool:
        """Check if signer has keys configured."""
        return self._private_key is not None

    def sign(self, message: bytes, trusted_comment: str = "") -> Signature:
        """Sign a message.

        Args:
            message: Message to sign
            trusted_comment: Optional trusted comment

        Returns:
            Signature object

        Raises:
            SigningError: If not configured or signing fails
        """
        if not self.is_configured():
            raise SigningError("No private key configured")

        if not self._public_key:
            raise SigningError("No public key available")

        if self._has_crypto and self._signing_key:
            # Use real Ed25519
            signature = self._signing_key.sign(message)
        else:
            # Fall back to HMAC-based deterministic signature
            # This provides tamper detection but not cryptographic non-repudiation
            signature = self._deterministic_sign(message)

        return Signature(
            signature=signature,
            public_key=self._public_key,
            algorithm=self.ALG_ED25519,
            trusted_comment=trusted_comment or f"timestamp:{hashlib.sha256(message).hexdigest()[:16]}",
        )

    def _deterministic_sign(self, message: bytes) -> bytes:
        """Create deterministic signature using HMAC."""
        # HMAC-SHA256 truncated to 64 bytes for Ed25519 compatibility
        import hmac

        sig = hmac.new(self._private_key, message, hashlib.sha256).digest()
        # Pad or truncate to 64 bytes
        if len(sig) < 64:
            sig = sig + b"\x00" * (64 - len(sig))
        return sig[:64]

    def verify(self, message: bytes, signature: Signature) -> bool:
        """Verify a signature.

        Args:
            message: Original message
            signature: Signature to verify

        Returns:
            True if valid, False otherwise
        """
        if not signature.public_key and not self._public_key:
            raise VerificationError("No public key available for verification")

        pub_key = signature.public_key or self._public_key

        if self._has_crypto:
            try:
                from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                    Ed25519PublicKey,
                )

                verify_key = Ed25519PublicKey.from_public_bytes(pub_key)
                verify_key.verify(signature.signature, message)
                return True
            except Exception:
                return False
        else:
            # Without cryptography library, we cannot do proper signature verification
            # The HMAC-based approach requires the private key, which the verifier doesn't have
            raise VerificationError(
                "Signature verification requires the 'cryptography' library. "
                "Install with: pip install cryptography"
            )

    def sign_file(self, file_path: Path, output_path: Path | None = None) -> Path:
        """Sign a file and write signature.

        Args:
            file_path: File to sign
            output_path: Where to write signature (default: file_path.sig)

        Returns:
            Path to signature file
        """
        if output_path is None:
            output_path = file_path.parent / f"{file_path.name}.sig"

        with open(file_path, "rb") as f:
            message = f.read()

        sig = self.sign(message, trusted_comment=f"file:{file_path.name}")

        with open(output_path, "wb") as f:
            f.write(sig.to_bytes())

        return output_path

    @classmethod
    def generate_keys(cls) -> tuple[bytes, bytes]:
        """Generate a new key pair.

        Returns:
            Tuple of (private_key, public_key) as bytes
        """
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PrivateKey,
            )

            private_key = Ed25519PrivateKey.generate()
            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
            public_bytes = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            return (private_bytes, public_bytes)
        except ImportError:
            # Generate deterministic keys using hash
            import secrets

            private_bytes = secrets.token_bytes(32)
            public_bytes = hashlib.sha256(private_bytes).digest()[:32]
            return (private_bytes, public_bytes)

    @classmethod
    def keys_to_env_format(cls, private_key: bytes, public_key: bytes) -> tuple[str, str]:
        """Convert keys to environment variable format.

        Returns:
            Tuple of (private_key_b64, public_key_b64)
        """
        return (
            base64.b64encode(private_key).decode("ascii"),
            base64.b64encode(public_key).decode("ascii"),
        )
