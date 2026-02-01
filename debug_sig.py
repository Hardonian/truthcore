"""Quick debug script for signature verification."""

from truthcore.provenance.signing import Signer
from truthcore.provenance.manifest import EvidenceManifest
from truthcore.provenance.verifier import BundleVerifier
from pathlib import Path
import tempfile

# Create a temp directory
tmp_path = Path(tempfile.mkdtemp())

# Create keys
private_key, public_key = Signer.generate_keys()
print(f"Private key: {private_key[:8].hex()}... ({len(private_key)} bytes)")
print(f"Public key: {public_key[:8].hex()}... ({len(public_key)} bytes)")

# Create bundle
bundle_dir = tmp_path / "bundle"
bundle_dir.mkdir()
(bundle_dir / "data.json").write_text('{"key": "value"}')

# Generate and sign manifest
manifest = EvidenceManifest.generate(bundle_dir)
manifest.write_json(bundle_dir / "evidence.manifest.json")

signer = Signer(private_key=private_key, public_key=public_key)
print(f"Signer._public_key: {signer._public_key[:8].hex() if signer._public_key else None}...")
print(f"Signer._has_crypto: {signer._has_crypto}")

signer.sign_file(bundle_dir / "evidence.manifest.json", bundle_dir / "evidence.sig")

# Verify
verifier = BundleVerifier(public_key=public_key)
print(f"Verifier.public_key: {verifier.public_key[:8].hex() if verifier.public_key else None}...")
print(f"Verifier._signer._public_key: {verifier._signer._public_key[:8].hex() if verifier._signer and verifier._signer._public_key else None}...")

result = verifier.verify(bundle_dir)
print(f"\nResult: {result}")
print(f"Valid: {result.valid}")
print(f"Signature valid: {result.signature_valid}")
print(f"Errors: {result.errors}")

# Cleanup
import shutil
shutil.rmtree(tmp_path)
