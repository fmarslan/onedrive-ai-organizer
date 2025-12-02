"""
Configuration helpers for the OneDrive AI Organizer project.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    """Holds the MSAL-related settings needed to connect to Microsoft Graph."""

    client_id: str
    authority: str
    output_dir: Path


def _prompt_client_id() -> str:
    """Prompt the user for the Azure Application (client) ID if it is missing."""
    try:
        return input("Azure Application (client) ID (MS_CLIENT_ID missing): ").strip()
    except EOFError:
        return ""


def _prompt_tenant() -> str:
    """Prompt the user for an Azure tenant if the env variable is not set."""
    try:
        return input("Azure tenant ID or domain (MS_TENANT missing, e.g. 'organizations'): ").strip()
    except EOFError:
        return ""


def load_config() -> Config:
    """
    Load configuration from environment variables (with interactive fallback).

    Returns:
        Config: The resolved client ID and authority URL.

    Raises:
        SystemExit: If no client ID is provided even after prompting.
    """
    client_id = os.environ.get("MS_CLIENT_ID", "").strip()
    if not client_id:
        client_id = _prompt_client_id()

    if not client_id:
        print("ERROR: CLIENT_ID is required. Configure MS_CLIENT_ID or enter it interactively.")
        raise SystemExit(1)

    tenant = os.environ.get("MS_TENANT", "").strip()
    if not tenant:
        tenant = _prompt_tenant()

    if not tenant:
        print("ERROR: Tenant ID is required. Provide MS_TENANT (e.g. 'organizations').")
        raise SystemExit(1)

    output_dir_raw = os.environ.get("OUTPUT_DIR", "").strip()
    if not output_dir_raw:
        try:
            output_dir_raw = input("Output directory for CSV/state files (default=./): ").strip()
        except EOFError:
            output_dir_raw = ""

    output_dir = Path(output_dir_raw or ".").expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    authority = f"https://login.microsoftonline.com/{tenant}"

    return Config(client_id=client_id, authority=authority, output_dir=output_dir)
