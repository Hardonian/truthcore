"""Buyer-facing, self-verifying evidence packet export."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from truthcore.replay.bundle import ReplayBundle


class EvidencePacketExporter:
    """Package a replay bundle with an index and human-readable replay instructions."""

    def export(self, bundle: ReplayBundle, output: Path) -> Path:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        files = sorted(p for p in bundle.bundle_dir.rglob("*") if p.is_file() and p.name != output.name)
        entries: list[dict[str, Any]] = []
        for file in files:
            rel = file.relative_to(bundle.bundle_dir).as_posix()
            entries.append(
                {"path": rel, "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "size": file.stat().st_size}
            )
        index = {
            "format": "truthcore-evidence-packet-v1",
            "run_id": bundle.manifest.run_id,
            "command": bundle.manifest.command,
            "verdict_source": "replay bundle",
            "files": entries,
        }
        readme = (
            "# Evidence packet\n\n"
            "This packet contains the original replay bundle and a content hash index.\n"
            "Verify each file against `evidence-index.json`, then replay with:\n\n"
            "```\ntruthctl replay --bundle <unpacked-directory> --out ./replay-results\n```\n"
        )
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in files:
                archive.write(file, file.relative_to(bundle.bundle_dir).as_posix())
            archive.writestr("evidence-index.json", json.dumps(index, indent=2, sort_keys=True) + "\n")
            archive.writestr("README.md", readme)
        return output
