"""Auto-update module for checking and downloading updates from GitHub."""
import sys
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, NamedTuple

import requests
from packaging import version

from utils import get_resource_path


GITHUB_REPO = "com55/SSML"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


class UpdateInfo(NamedTuple):
    """Information about an available update."""
    current_version: str
    latest_version: str
    download_url: str
    release_notes: str
    release_name: str


def is_running_as_exe() -> bool:
    """Check if the application is running as a Nuitka-compiled executable."""
    # Nuitka sets __compiled__ attribute, not sys.frozen
    return "__compiled__" in dir()


def get_current_version() -> str:
    """Get the current application version from VERSION file or pyproject.toml."""
    # When running as Nuitka-compiled exe, read from VERSION file
    if is_running_as_exe():
        # VERSION file is next to the executable
        version_file = get_resource_path("VERSION")
        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip()
        # Fallback to hardcoded version
        return "0.0.0"
    
    # When running as script, read from pyproject.toml
    try:
        pyproject_path = get_resource_path("pyproject.toml")
        if pyproject_path.exists():
            content = pyproject_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.strip().startswith("version"):
                    # Extract version from: version = "0.1.1-beta"
                    return line.split("=")[1].strip().strip('"\'')
    except Exception:
        pass
    
    return "0.0.0"


def normalize_version(ver: str) -> str:
    """Normalize version string for comparison (e.g., v0.1.1-beta -> 0.1.1b0)."""
    ver = ver.strip().lstrip("v")
    # Replace -beta, -alpha etc. with PEP 440 compatible format
    ver = ver.replace("-beta", "b0").replace("-alpha", "a0").replace("-rc", "rc")
    return ver


def check_for_updates() -> UpdateInfo | None:
    """
    Check GitHub for available updates.
    
    Returns:
        UpdateInfo if an update is available, None otherwise.
    """
    try:
        response = requests.get(
            GITHUB_API_URL,
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=10
        )
        response.raise_for_status()
        
        release_data = response.json()
        latest_version = release_data.get("tag_name", "")
        release_notes = release_data.get("body", "")
        release_name = release_data.get("name", latest_version)
        
        # Find the .zip asset (release is packaged as zip)
        download_url = ""
        assets = release_data.get("assets", [])
        for asset in assets:
            asset_name = asset.get("name", "")
            if asset_name.endswith(".zip"):
                download_url = asset.get("browser_download_url", "")
                break
        
        if not download_url:
            # No zip found, can't update
            return None
        
        current = get_current_version()
        
        # Compare versions
        try:
            current_ver = version.parse(normalize_version(current))
            latest_ver = version.parse(normalize_version(latest_version))
            
            if latest_ver > current_ver:
                return UpdateInfo(
                    current_version=current,
                    latest_version=latest_version,
                    download_url=download_url,
                    release_notes=release_notes,
                    release_name=release_name
                )
        except version.InvalidVersion:
            # If version parsing fails, do string comparison
            if normalize_version(latest_version) != normalize_version(current):
                return UpdateInfo(
                    current_version=current,
                    latest_version=latest_version,
                    download_url=download_url,
                    release_notes=release_notes,
                    release_name=release_name
                )
        
        return None
        
    except requests.RequestException:
        # Network error, can't check for updates
        return None
    except Exception:
        # Unexpected error
        return None


def download_update(url: str, progress_callback: Callable[[int, int], None] | None = None) -> Path | None:
    """
    Download the update zip file to a temporary location and extract it.
    
    Args:
        url: Download URL for the update (should be a .zip file)
        progress_callback: Optional callback(downloaded, total) for progress updates
        
    Returns:
        Path to extracted folder containing the new exe, or None if failed
    """
    try:
        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()
        
        total_size = int(response.headers.get("content-length", 0))
        
        # Create temp directory
        temp_dir = Path(tempfile.gettempdir()) / "ssml_update"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Download zip file
        zip_file = temp_dir / "update.zip"
        
        downloaded = 0
        with open(zip_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        progress_callback(downloaded, total_size)
        
        # Extract zip file
        extract_dir = temp_dir / "extracted"
        if extract_dir.exists():
            import shutil
            shutil.rmtree(extract_dir)
        
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Find the folder containing exe (structure: StellaSoraModLauncher/StellaSoraModLauncher.exe)
        for item in extract_dir.iterdir():
            if item.is_dir():
                exe_path = item / "StellaSoraModLauncher.exe"
                if exe_path.exists():
                    return item
        
        # If no subfolder, check root
        if (extract_dir / "StellaSoraModLauncher.exe").exists():
            return extract_dir
        
        return None
        
    except Exception:
        return None


def apply_update(update_folder: Path) -> bool:
    """
    Apply the update by replacing the current executable.
    
    Since Nuitka onefile mode embeds all resources in the exe,
    we only need to replace the exe file. User data (Mods/, Backups/, 
    config.ini, ModsStatus.json) is preserved as they are outside the exe.
    
    This creates a batch script that:
    1. Waits for the current process to exit
    2. Replaces the exe file
    3. Starts the new exe
    4. Cleans up temp files
    
    Returns:
        True if the update process was started successfully
    """
    if not is_running_as_exe():
        return False
    
    current_exe = Path(sys.argv[0]).resolve()
    new_exe = update_folder / "StellaSoraModLauncher.exe"
    
    if not new_exe.exists():
        return False
    
    # Create update batch script
    # Onefile exe has all resources embedded, so we only need to copy the exe
    batch_content = f'''@echo off
echo Updating Stella Sora Mod Launcher...
timeout /t 2 /nobreak > nul

REM Replace exe file (all resources are embedded in onefile mode)
copy /y "{new_exe}" "{current_exe}"

REM Start new version
start "" "{current_exe}"

REM Cleanup temp files
timeout /t 3 /nobreak > nul
rmdir /s /q "{update_folder.parent}"

REM Delete this batch file
del "%~f0"
'''
    
    batch_file = update_folder.parent / "update.bat"
    batch_file.write_text(batch_content, encoding="utf-8")
    
    # Run the batch script in minimized window
    subprocess.Popen(
        f'start "" /min "{batch_file}"',
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    
    return True


