"""
This script will take from the OS the variabels galaxy_url, galaxy_token and publish the collection to Ansible Galaxy.
It uses ansible-galaxy collection publish command.
"""

import os
import subprocess
import sys
from pathlib import Path

# get the galaxy_url from the environment variables
GALAXY_URL = os.getenv("GALAXY_URL")
if not GALAXY_URL:
    print("ERROR: GALAXY_URL environment variable not set", file=sys.stderr)
    sys.exit(1)

# get the galaxy_token from the environment variables
GALAXY_TOKEN = os.getenv("GALAXY_TOKEN")
if not GALAXY_TOKEN:
    print("ERROR: GALAXY_TOKEN environment variable not set", file=sys.stderr)
    sys.exit(1)


def create_collection_archive(collection_dir, output_dir):
    """
    Create a tar.gz archive of the Ansible collection.
    
    Args:
        collection_dir: Path to the collection directory
        output_dir: Directory where the archive will be created
    Returns:
        Path to the created archive
    """
    result = subprocess.run([
        "ansible-galaxy", "collection", "build",
        str(collection_dir),
        "-f",
        "--output-path", str(output_dir)
    ], check=True, capture_output=True, text=True)
    
    # Parse the output to find the actual tarball path
    for line in result.stdout.split('\n'):
        if line.startswith("Created collection"):
            parts = line.split(" at ")
            if len(parts) == 2:
                return Path(parts[1].strip())
    
    # Fallback: look for .tar.gz files in output directory
    tarball_files = list(Path(output_dir).glob("*.tar.gz"))
    if tarball_files:
        return tarball_files[0]
    
    raise RuntimeError("Could not find created collection archive")

def upload_collection(archive_path):
    """
    Upload the collection archive to Ansible Galaxy.
    
    Args:
        archive_path: Path to the collection archive
    """
    subprocess.run([
        "ansible-galaxy", "collection", "publish",
        str(archive_path),
        "--api-key", GALAXY_TOKEN,
        "--server", GALAXY_URL
    ], check=True)


def run_galaxy_importer(archive_path):
    """
    Run galaxy_importer on the collection artifact before upload.

    Args:
        archive_path: Path to the collection archive
    """
    subprocess.run([
        sys.executable, "-m", "galaxy_importer.main",
        str(archive_path)
    ], check=True)



def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <collection_directory>")
        print(f"Example: {sys.argv[0]} /path/to/collection")
        return 1
    
    collection_dir = Path(sys.argv[1]).resolve()

    if not collection_dir.exists() or not collection_dir.is_dir():
        print(f"ERROR: Collection directory not found or is not a directory: {collection_dir}")
        return 1

    # Use parent directory as output directory for the build
    output_dir = collection_dir.parent

    print(f"Creating collection archive in: {output_dir}")
    archive_path = create_collection_archive(collection_dir, output_dir)
    print(f"Created collection archive at: {archive_path}")

    print(f"Running galaxy_importer on: {archive_path}")
    run_galaxy_importer(archive_path)

    print(f"Uploading collection archive to Ansible Galaxy: {archive_path}")
    upload_collection(archive_path)

    print("Collection successfully published to Ansible Galaxy.")
    return 0

if __name__ == "__main__":
    sys.exit(main())    