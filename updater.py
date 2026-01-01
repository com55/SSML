"""Auto-update module for checking and downloading updates from GitHub."""
import logging
import sys
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, NamedTuple

import requests


from utils import get_resource_path

logger = logging.getLogger(__name__)


GITHUB_REPO = "com55/SSML"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_API_RELEASES = f"https://api.github.com/repos/{GITHUB_REPO}/releases"


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
    return "__compiled__" in globals()


def get_current_version() -> str:
    """Get the current application version from VERSION file or pyproject.toml."""
    # When running as Nuitka-compiled exe, read from VERSION file
    if is_running_as_exe():
        # VERSION file is next to the executable
        version_file = get_resource_path("VERSION")
        if version_file.exists():
            return version_file.read_text(encoding="utf-8-sig").strip()
        # Fallback to hardcoded version
        return "0.0.0"
    
    # When running as script, read from pyproject.toml
    try:
        pyproject_path = get_resource_path("pyproject.toml")
        if pyproject_path.exists():
            content = pyproject_path.read_text(encoding="utf-8-sig")
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


def check_for_updates(include_prerelease: bool = False) -> UpdateInfo | None:
    """
    Check GitHub for available updates.
    
    Args:
        include_prerelease: If True, include prerelease versions (alpha, beta, rc).
                           If False (default), only check stable releases.
    
    Returns:
        UpdateInfo if an update is available, None otherwise.
    """
    try:
        if include_prerelease:
            # Fetch all releases and get the first one (latest including prereleases)
            api_url = GITHUB_API_RELEASES
            logger.debug(f"Checking for updates (including prereleases) from {api_url}")
        else:
            # Fetch only the latest stable release
            api_url = GITHUB_API_LATEST
            logger.debug(f"Checking for updates (stable only) from {api_url}")
        
        response = requests.get(
            api_url,
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=10
        )
        response.raise_for_status()
        
        # Handle response - list for /releases, dict for /releases/latest
        data = response.json()
        if include_prerelease:
            if not data:
                return None
            release_data = data[0]  # First release is the latest
        else:
            release_data = data
        
        latest_version = release_data.get("tag_name", "")
        release_notes = release_data.get("body", "")
        release_name = release_data.get("name", latest_version)
        is_prerelease = release_data.get("prerelease", False)
        
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
        
        current = current.lstrip("v")
        latest_version = latest_version.lstrip("v")
        logger.debug(f"Current version: {current}")
        logger.debug(f"Latest version: {latest_version}")
        
        # Compare versions using numeric tuple extraction
        try:
            import re
            def get_version_tuple(v_str: str):
                # Extract numeric part (e.g. 0.1.3.6 from v0.1.3.6-beta)
                match = re.search(r'(\d+(\.\d+)*)', v_str)
                if match:
                    parts = match.group(0).split('.')
                    return tuple(map(int, parts))
                return (0,)

            current_tuple = get_version_tuple(current)
            latest_tuple = get_version_tuple(latest_version)
            
            logger.debug(f"Version comparison: current='{current}' -> {current_tuple}, latest='{latest_version}' -> {latest_tuple}")
            
            if latest_tuple > current_tuple:
                # Add prerelease indicator to release name if applicable
                if is_prerelease and not any(x in release_name.lower() for x in ["alpha", "beta", "rc"]):
                    release_name = f"{release_name} (Pre-release)"
                
                logger.info(f"Update available: {current} -> {latest_version}")
                return UpdateInfo(
                    current_version=current,
                    latest_version=latest_version,
                    download_url=download_url,
                    release_notes=release_notes,
                    release_name=release_name
                )
        except Exception as e:
            logger.error(f"Error during version comparison: {e}", exc_info=True)
            return None
        
        return None
        
    except requests.RequestException as e:
        logger.warning(f"Network error checking for updates: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error checking for updates: {e}", exc_info=True)
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
        logger.info(f"Downloading update from {url}")
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
        
    except Exception as e:
        logger.error(f"Failed to download update: {e}", exc_info=True)
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
        logger.error(f"New exe not found in update folder: {new_exe}")
        return False
    
    logger.info(f"Applying update: replacing {current_exe} with {new_exe}")
    
    import os
    current_pid = os.getpid()
    
    # Create update batch script with retry mechanism
    # Onefile exe has all resources embedded, so we only need to copy the exe
    batch_content = f'''@echo off
setlocal enabledelayedexpansion
echo Updating Stella Sora Mod Launcher...

REM Force kill the old process by PID
taskkill /F /PID {current_pid} >nul 2>&1

REM Wait for process to fully terminate (max 10 seconds)
set /a retries=0
:WAIT_FOR_EXIT
tasklist /FI "PID eq {current_pid}" 2>nul | find "{current_pid}" >nul
if %errorlevel% equ 0 (
    set /a retries+=1
    if !retries! lss 20 (
        timeout /t 1 /nobreak >nul
        goto WAIT_FOR_EXIT
    )
    echo Warning: Old process still running, continuing anyway...
)

REM Copy with retry loop (max 10 retries, 1 second apart)
set /a retries=0
:COPY_RETRY
copy /y "{new_exe}" "{current_exe}" >nul 2>&1
if %errorlevel% neq 0 (
    set /a retries+=1
    if !retries! lss 10 (
        echo Retry %retries%/10...
        timeout /t 1 /nobreak >nul
        goto COPY_RETRY
    )
    echo ERROR: Failed to copy update after 10 retries.
    pause
    goto END
)

echo Update completed successfully!

REM Start new version with flag to skip update check (use /B to hide console)
start "" /B "{current_exe}" --after-update

REM Cleanup temp files
timeout /t 3 /nobreak >nul
rmdir /s /q "{update_folder.parent}" >nul 2>&1

:END
REM Delete this batch file
del "%~f0"
'''
    
    batch_file = update_folder.parent / "update.bat"
    batch_file.write_text(batch_content, encoding="utf-8")
    
    # Run the batch script completely hidden (no console window)
    CREATE_NO_WINDOW = 0x08000000
    subprocess.Popen(
        ['cmd', '/c', str(batch_file)],
        creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    
    return True


