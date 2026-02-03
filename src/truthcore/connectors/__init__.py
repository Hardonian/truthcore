"""Connectors module for truth-core - input source adapters."""

from __future__ import annotations

from truthcore.connectors.base import BaseConnector, ConnectorConfig, ConnectorResult
from truthcore.connectors.http import HTTPConnector
from truthcore.connectors.local import LocalConnector

# Optional connectors - import only if available
try:
    from truthcore.connectors.github import GitHubActionsConnector
except ImportError:
    GitHubActionsConnector = None  # type: ignore[misc, assignment]

try:
    from truthcore.connectors.s3 import S3Connector
except ImportError:
    S3Connector = None  # type: ignore[misc, assignment]

__all__ = [
    "BaseConnector",
    "ConnectorConfig",
    "ConnectorResult",
    "LocalConnector",
    "HTTPConnector",
    "GitHubActionsConnector",
    "S3Connector",
    "get_connector",
    "list_connectors",
]


def get_connector(name: str, config: ConnectorConfig | None = None) -> BaseConnector | None:
    """Get a connector by name.
    
    Args:
        name: Connector name (local, http, github-actions, s3)
        config: Optional connector configuration
        
    Returns:
        Connector instance or None if not available
    """
    connectors = {
        "local": LocalConnector,
        "http": HTTPConnector,
        "github-actions": GitHubActionsConnector,
        "s3": S3Connector,
    }

    connector_class = connectors.get(name)
    if connector_class is None:
        return None

    try:
        instance = connector_class(config)
        return instance if instance.is_available else None
    except Exception:
        return None


def list_connectors() -> list[dict[str, str | bool]]:
    """List all available connectors.
    
    Returns:
        List of connector info dicts with name and available status
    """
    result = []

    for name in ["local", "http", "github-actions", "s3"]:
        connector = get_connector(name)
        result.append({
            "name": name,
            "available": connector is not None and connector.is_available,
        })

    return result
