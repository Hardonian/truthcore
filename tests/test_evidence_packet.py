import json
from pathlib import Path

from truthcore.replay import EvidencePacketExporter, ReplayBundle


def test_evidence_packet_contains_hash_index(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    (bundle_dir / "inputs").mkdir(parents=True)
    (bundle_dir / "outputs").mkdir()
    manifest = {
        "run_id": "run-1", "command": "judge", "timestamp": "2026-01-01T00:00:00Z",
        "truthcore_version": "0.2.0", "config": {"hash": "h"},
        "inputs": {"directory": str(bundle_dir / "inputs"), "files": []},
        "cache": {}, "execution": {},
    }
    (bundle_dir / "run_manifest.json").write_text(json.dumps(manifest))
    (bundle_dir / "outputs" / "verdict.json").write_text('{"verdict":"pass"}\n')
    bundle = ReplayBundle.load(bundle_dir)
    packet = EvidencePacketExporter().export(bundle, tmp_path / "packet.zip")
    assert packet.exists()
    import zipfile
    with zipfile.ZipFile(packet) as archive:
        index = json.loads(archive.read("evidence-index.json"))
        assert index["run_id"] == "run-1"
        assert any(item["path"] == "outputs/verdict.json" for item in index["files"])
        assert "truthctl replay" in archive.read("README.md").decode()
