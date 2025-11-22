#!/usr/bin/env python3
"""
Download QE tutorial examples from GitHub.

Downloads from: https://github.com/quantumNerd/Quantum-Espresso-Tutorial-2019-Projects
"""

import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))


def download_tutorial_examples(
    output_dir: Optional[Path] = None,
    force: bool = False
) -> Path:
    """
    Download QE tutorial examples from GitHub.
    
    Args:
        output_dir: Output directory (default: temp/downloads/qe_tutorial_examples)
        force: Force re-download even if directory exists
    
    Returns:
        Path to downloaded directory
    """
    if output_dir is None:
        output_dir = project_root / "temp" / "downloads" / "qe_tutorial_examples"
    
    output_dir = Path(output_dir)
    
    # Check if already exists
    if output_dir.exists() and not force:
        print(f"Tutorial examples already exist at: {output_dir}")
        return output_dir
    
    # Create parent directory
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove existing directory if force
    if output_dir.exists() and force:
        print(f"Removing existing directory: {output_dir}")
        shutil.rmtree(output_dir)
    
    # Download using git clone
    repo_url = "https://github.com/quantumNerd/Quantum-Espresso-Tutorial-2019-Projects.git"
    
    print(f"Downloading QE tutorial examples from: {repo_url}")
    print(f"Destination: {output_dir}")
    
    try:
        # Clone repository
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(output_dir)],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✅ Successfully downloaded to: {output_dir}")
        return output_dir
    except subprocess.CalledProcessError as e:
        print(f"❌ Error downloading: {e}")
        print(f"   stdout: {e.stdout}")
        print(f"   stderr: {e.stderr}")
        raise
    except FileNotFoundError:
        # Git not available, try alternative method
        print("⚠️  Git not found, trying alternative download method...")
        return download_with_urllib(repo_url, output_dir)


def download_with_urllib(repo_url: str, output_dir: Path) -> Path:
    """
    Alternative download method using urllib (for zip download).
    
    Note: GitHub doesn't provide direct zip URLs for repos, so this is a fallback.
    """
    import urllib.request
    import zipfile
    import tempfile
    
    # GitHub provides zip download via: https://github.com/user/repo/archive/refs/heads/branch.zip
    zip_url = repo_url.replace(".git", "/archive/refs/heads/master.zip")
    
    print(f"Downloading zip from: {zip_url}")
    
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
        try:
            urllib.request.urlretrieve(zip_url, tmp_file.name)
            
            # Extract zip
            with zipfile.ZipFile(tmp_file.name, 'r') as zip_ref:
                zip_ref.extractall(output_dir.parent)
            
            # Rename extracted directory
            extracted_dir = output_dir.parent / "Quantum-Espresso-Tutorial-2019-Projects-master"
            if extracted_dir.exists():
                if output_dir.exists():
                    shutil.rmtree(output_dir)
                extracted_dir.rename(output_dir)
            
            print(f"✅ Successfully downloaded to: {output_dir}")
            return output_dir
        finally:
            # Clean up temp file
            Path(tmp_file.name).unlink(missing_ok=True)


def ensure_tutorial_examples(
    output_dir: Optional[Path] = None,
    force: bool = False
) -> Path:
    """
    Ensure tutorial examples are available, download if needed.
    
    Args:
        output_dir: Output directory
        force: Force re-download
    
    Returns:
        Path to tutorial examples directory
    """
    if output_dir is None:
        output_dir = project_root / "temp" / "downloads" / "qe_tutorial_examples"
    
    output_dir = Path(output_dir)
    
    # Check if exists and has content
    if output_dir.exists() and not force:
        # Check if it's a valid git repo or has content
        if (output_dir / ".git").exists() or any(output_dir.iterdir()):
            return output_dir
    
    # Download
    return download_tutorial_examples(output_dir, force=force)


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Download QE tutorial examples from GitHub"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: temp/downloads/qe_tutorial_examples)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if directory exists"
    )
    
    args = parser.parse_args()
    
    try:
        output_dir = ensure_tutorial_examples(args.output_dir, force=args.force)
        print(f"\n✅ Tutorial examples available at: {output_dir}")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

