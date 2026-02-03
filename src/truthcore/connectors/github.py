"""GitHub Actions artifacts connector for truth-core."""

from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from truthcore.connectors.base import BaseConnector, ConnectorConfig, ConnectorResult


class GitHubActionsConnector(BaseConnector):
    """Connector for GitHub Actions workflow artifacts.
    
    Downloads artifacts from GitHub Actions runs using the GitHub API.
    Requires a GitHub token with appropriate permissions.
    
    Example source format:
        owner/repo/workflow_run_id/artifact_name
        or
        github://owner/repo/run_id/artifact_name
    """

    GITHUB_API_URL = "https://api.github.com"

    def __init__(self, config: ConnectorConfig | None = None, token: str | None = None):
        """Initialize with optional GitHub token.
        
        Args:
            config: Connector configuration
            token: GitHub personal access token (or from GITHUB_TOKEN env var)
        """
        super().__init__(config)
        self._token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    @property
    def name(self) -> str:
        return "github-actions"

    @property
    def is_available(self) -> bool:
        """Check if GitHub token is configured."""
        return self._token is not None and len(self._token) > 0

    def fetch(self, source: str, destination: Path) -> ConnectorResult:
        """Download artifact from GitHub Actions.
        
        Args:
            source: Source in format "owner/repo/run_id/artifact_name" or
                   "github://owner/repo/run_id/artifact_name"
            destination: Destination directory for extracted artifact
            
        Returns:
            ConnectorResult with status and file list
        """
        if not self.is_available:
            return ConnectorResult(
                success=False,
                error="GitHub token not configured. Set GITHUB_TOKEN or GH_TOKEN environment variable."
            )

        # Parse source
        parsed = self._parse_source(source)
        if not parsed:
            return ConnectorResult(
                success=False,
                error=f"Invalid source format: {source}. Expected: owner/repo/run_id/artifact_name"
            )

        owner, repo, run_id, artifact_name = parsed

        destination.mkdir(parents=True, exist_ok=True)

        try:
            # Get artifact download URL
            download_url = self._get_artifact_download_url(owner, repo, run_id, artifact_name)
            if not download_url:
                return ConnectorResult(
                    success=False,
                    error=f"Artifact '{artifact_name}' not found in run {run_id}"
                )

            # Download and extract
            return self._download_and_extract(download_url, destination, owner, repo, run_id, artifact_name)

        except HTTPError as e:
            if e.code == 401:
                return ConnectorResult(success=False, error="GitHub authentication failed (401)")
            elif e.code == 404:
                return ConnectorResult(success=False, error="Artifact or repository not found (404)")
            elif e.code == 403:
                return ConnectorResult(success=False, error="GitHub API rate limit exceeded (403)")
            return ConnectorResult(success=False, error=f"GitHub API error: {e.code}")
        except URLError as e:
            return ConnectorResult(success=False, error=f"Network error: {e.reason}")
        except Exception as e:
            return ConnectorResult(success=False, error=f"Error: {e}")

    def _parse_source(self, source: str) -> tuple[str, str, str, str] | None:
        """Parse source string into components.
        
        Args:
            source: Source string
            
        Returns:
            Tuple of (owner, repo, run_id, artifact_name) or None if invalid
        """
        # Remove github:// prefix if present
        if source.startswith("github://"):
            source = source[9:]

        parts = source.split("/")
        if len(parts) < 4:
            return None

        # Support both 4-part and 5-part (with optional empty strings) formats
        # owner/repo/run_id/artifact_name
        owner = parts[0]
        repo = parts[1]
        run_id = parts[2]
        artifact_name = parts[3]

        if not all([owner, repo, run_id, artifact_name]):
            return None

        return owner, repo, run_id, artifact_name

    def _get_artifact_download_url(
        self, owner: str, repo: str, run_id: str, artifact_name: str
    ) -> str | None:
        """Get artifact download URL from GitHub API.
        
        Args:
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID
            artifact_name: Artifact name
            
        Returns:
            Download URL or None if not found
        """
        url = f"{self.GITHUB_API_URL}/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts"

        req = Request(url)
        req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")

        with urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        # Find matching artifact
        for artifact in data.get("artifacts", []):
            if artifact.get("name") == artifact_name:
                return artifact.get("archive_download_url")

        return None

    def _download_and_extract(
        self, download_url: str, destination: Path, owner: str, repo: str, run_id: str, artifact_name: str
    ) -> ConnectorResult:
        """Download artifact zip and extract to destination.
        
        Args:
            download_url: URL to download artifact zip
            destination: Destination directory
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID
            artifact_name: Artifact name
            
        Returns:
            ConnectorResult
        """
        req = Request(download_url)
        req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("Accept", "application/vnd.github+json")

        files_extracted: list[str] = []
        total_size = 0
        errors: list[str] = []

        with urlopen(req, timeout=60) as response:
            zip_data = response.read()

        # Extract zip
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            for member in zf.namelist():
                # Skip directories
                if member.endswith("/"):
                    continue

                # Validate path
                if not self.validate_path(member):
                    errors.append(f"Skipped blocked file: {member}")
                    continue

                # Check file count
                if len(files_extracted) >= self.config.max_files:
                    errors.append(f"Reached max file limit ({self.config.max_files})")
                    break

                # Get file info
                info = zf.getinfo(member)

                # Check size limit
                if not self.check_size_limit(total_size, info.file_size):
                    errors.append(f"Reached max size limit ({self.config.max_size_bytes} bytes)")
                    break

                # Extract file
                dest_path = destination / member
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                with zf.open(member) as src, open(dest_path, "wb") as dst:
                    shutil_data = src.read()
                    dst.write(shutil_data)

                files_extracted.append(member)
                total_size += info.file_size

        return ConnectorResult(
            success=True,
            local_path=destination,
            files=files_extracted,
            metadata={
                "source": f"github://{owner}/{repo}/{run_id}/{artifact_name}",
                "owner": owner,
                "repo": repo,
                "run_id": run_id,
                "artifact_name": artifact_name,
                "files_extracted": len(files_extracted),
                "total_bytes": total_size,
                "errors": errors if errors else None,
            }
        )
