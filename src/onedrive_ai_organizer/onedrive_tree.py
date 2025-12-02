"""
Core logic for exporting the full OneDrive tree into a CSV file.
"""

from __future__ import annotations

import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import msal
import pandas as pd
import requests
from tqdm import tqdm

from .config import Config, load_config

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
SCOPES = ["Files.Read.All"]
ORIGINAL_STRUCTURE_FILE = "original_structure.txt"
RECOMMENDED_STRUCTURE_FILE = "recommended_structure.txt"
STATE_FILE = "scan_state.json"


def acquire_token_device_code(config: Config) -> str:
    """
    Authenticate via MSAL device code flow and return an access token.

    The printed instructions match the previous single-file script to preserve UX.
    """
    app = msal.PublicClientApplication(config.client_id, authority=config.authority)
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise RuntimeError("Failed to start the device authorization flow. Check your Azure app settings.")

    print("\n=== Authorization steps ===\n")
    print(flow["message"])
    print("\nContinue here after you approve the request in the browser...\n")

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise RuntimeError(f"Failed to acquire access token: {result}")

    print("✅ Access token received.\n")
    return result["access_token"]


def graph_get(url: str, access_token: str, params: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    """
    Execute a Microsoft Graph GET request, handling pagination automatically.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    items: list[dict[str, Any]] = []

    while url:
        while True:
            resp = requests.get(url, headers=headers, params=params)
            if resp.status_code in {429, 503}:
                retry_after_raw = resp.headers.get("Retry-After", "").strip()
                try:
                    retry_seconds = max(1, int(float(retry_after_raw)))
                except ValueError:
                    retry_seconds = 2
                print(f"Hit Microsoft Graph rate limit ({resp.status_code}). Sleeping {retry_seconds}s...")
                time.sleep(retry_seconds)
                continue

            if resp.status_code != 200:
                print("Error:", resp.status_code, resp.text)
                resp.raise_for_status()
            break

        data = resp.json()
        items.extend(data.get("value", []))
        url = data.get("@odata.nextLink")
        params = None  # nextLink already encodes pagination params

        time.sleep(0.1)  # avoid hammering the API unnecessarily

    return items


def walk_onedrive(access_token: str) -> tuple[str, list[dict[str, Any]]]:
    """
    Traverse the user's OneDrive hierarchy iteratively and return all items.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    root_resp = requests.get(f"{GRAPH_BASE_URL}/me/drive/root", headers=headers)
    root_resp.raise_for_status()
    root = root_resp.json()

    root_id = root["id"]
    root_name = root.get("name", "root")
    print(f"Root folder: {root_name} (id={root_id})")
    print("Scanning the full tree. This may take a while...\n")

    results: list[dict[str, Any]] = []
    stack: list[tuple[str, str]] = [(root_id, "")]
    progress = tqdm(desc="Scanning OneDrive tree", unit="item")

    while stack:
        current_id, current_path = stack.pop()

        children_url = f"{GRAPH_BASE_URL}/me/drive/items/{current_id}/children"
        children = graph_get(children_url, access_token)

        for child in children:
            name = child.get("name")
            is_folder = "folder" in child
            size = child.get("size", 0)
            last_modified = child.get("lastModifiedDateTime")
            item_id = child.get("id")
            web_url = child.get("webUrl")

            full_path = f"{current_path}/{name}" if current_path else name

            results.append(
                {
                    "id": item_id,
                    "path": full_path,
                    "name": name,
                    "is_folder": is_folder,
                    "size": size,
                    "last_modified": last_modified,
                    "web_url": web_url,
                }
            )
            progress.update(1)

            if is_folder:
                stack.append((item_id, full_path))

    progress.close()
    print(f"✅ Scan finished. Total items: {len(results)}")
    return root_name, results


def export_tree_to_csv(items: list[dict[str, Any]], output_file: Path) -> None:
    """
    Persist the collected OneDrive entries to a CSV file using UTF-8 encoding.
    """
    df = pd.DataFrame(items)
    df.to_csv(output_file, index=False, encoding="utf-8")


def _prompt_classification_mode() -> int:
    """Ask the user which classification workflow should run."""
    print("\n=== Choose a classification flow ===")
    print("1) Analyze the structure and generate an automatic recommendation")
    print("2) Use an existing classification file (coming soon)")

    while True:
        choice = input("Select 1 or 2: ").strip()
        if choice in {"1", "2"}:
            return int(choice)
        print("Please type only 1 or 2.")


def _format_original_structure(items: list[dict[str, Any]], root_name: str) -> str:
    """Return a readable, indented representation of the existing structure."""
    sorted_items = sorted(items, key=lambda item: item["path"].lower())
    lines = [
        "Current OneDrive structure",
        f"Root: {root_name}",
        "",
        f"{root_name}/",
    ]

    for item in sorted_items:
        path = item.get("path", "")
        if not path:
            continue

        depth = path.count("/") + 1
        indent = "    " * depth
        suffix = "/" if item.get("is_folder") else ""
        lines.append(f"{indent}- {item.get('name', 'unnamed')}{suffix}")

    return "\n".join(lines) + "\n"


CATEGORY_EXTENSIONS: dict[str, set[str]] = {
    "Documents": {"pdf", "doc", "docx", "txt", "rtf", "odt"},
    "Spreadsheets": {"xls", "xlsx", "ods", "csv"},
    "Presentations": {"ppt", "pptx", "key", "odp"},
    "Images": {"jpg", "jpeg", "png", "gif", "bmp", "tiff", "svg", "webp", "heic"},
    "Videos": {"mp4", "mov", "avi", "mkv", "wmv"},
    "Audio": {"mp3", "wav", "aac", "flac", "ogg"},
    "Archives": {"zip", "rar", "7z", "tar", "gz"},
    "Data": {"json", "xml", "yaml", "yml", "parquet"},
    "Code": {"py", "js", "ts", "java", "cs", "cpp", "ipynb"},
}


def _categorize_file(name: str) -> str:
    """Map a filename to a suggested high-level category."""
    ext = Path(name).suffix.lower().lstrip(".")
    if not ext:
        return "Misc"

    for category, extensions in CATEGORY_EXTENSIONS.items():
        if ext in extensions:
            return category
    return "Misc"


def _format_recommended_structure(items: list[dict[str, Any]], root_name: str) -> str:
    """Return a simplified target structure suggestion."""
    files_by_category: dict[str, list[str]] = defaultdict(list)
    for item in items:
        if item.get("is_folder"):
            continue
        name = item.get("name") or ""
        category = _categorize_file(name)
        files_by_category[category].append(item.get("path", name))

    top_levels = sorted({item["path"].split("/")[0] for item in items if item.get("path")})
    lines = [
        "Suggested simplified structure",
        f"Reference root: {root_name}",
        "",
        "Current top-level folders:",
    ]
    for folder in top_levels:
        lines.append(f"- {folder}/")

    lines.append("")
    lines.append("Suggested new parent folders with sample files:")

    for category in sorted(files_by_category.keys()):
        paths = files_by_category[category]
        lines.append(f"{category}/  (files: {len(paths)})")
        for sample in paths[:3]:
            lines.append(f"    • sample: {sample}")
        lines.append("    • action: move related files into this folder")

    if "Misc" not in files_by_category:
        lines.append("Misc/  (files: 0)")
        lines.append("    • action: catch-all for uncategorized items")

    lines.append("")
    lines.append("Note: The suggestion is based on file extensions. Review the content and tailor")
    lines.append("folder names if needed.")

    return "\n".join(lines) + "\n"


def _write_text_file(path: Path, content: str) -> None:
    """Persist helper."""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _write_state_file(path: Path, state: dict[str, Any]) -> None:
    """Write scan metadata so runs can resume or be audited."""
    import json

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)


def _run_option_auto_classification(config: Config) -> None:
    """Execute option 1: crawl tree, export CSV, and produce structure summaries."""
    start_time = time.time()
    access_token = acquire_token_device_code(config)
    root_name, results = walk_onedrive(access_token)
    csv_path = config.output_dir / "onedrive_tree.csv"
    export_tree_to_csv(results, csv_path)

    original_text = _format_original_structure(results, root_name)
    recommendation_text = _format_recommended_structure(results, root_name)
    original_path = config.output_dir / ORIGINAL_STRUCTURE_FILE
    recommended_path = config.output_dir / RECOMMENDED_STRUCTURE_FILE
    _write_text_file(original_path, original_text)
    _write_text_file(recommended_path, recommendation_text)

    state_path = config.output_dir / STATE_FILE
    state_payload = {
        "root_name": root_name,
        "total_items": len(results),
        "csv_path": str(csv_path),
        "original_structure_path": str(original_path),
        "recommended_structure_path": str(recommended_path),
        "duration_seconds": round(time.time() - start_time, 2),
    }
    _write_state_file(state_path, state_payload)

    print(f"\n✅ Saved tree snapshot to '{csv_path}'.")
    print(f"✅ Wrote '{original_path.name}' and '{recommended_path.name}'. Review them side by side inside {config.output_dir}.")
    print(f"✅ State file stored at '{state_path}' to track progress.")


def _run_option_existing_classification(_: Config) -> None:
    """Placeholder for option 2."""
    print("\nOption 2 (use existing classification) is not implemented yet. Stay tuned.")


def run() -> None:
    """
    CLI entry point used by main.py.
    """
    config = load_config()
    choice = _prompt_classification_mode()

    if choice == 1:
        _run_option_auto_classification(config)
    else:
        _run_option_existing_classification(config)
