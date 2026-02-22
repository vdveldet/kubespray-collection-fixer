"""
Build the kubespray ansible collection inside the container.

All work happens under /data.
"""

import os
import shutil
import subprocess
from pathlib import Path
import logging
import sys


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

missing_envs = [
    name for name in ("GALAXY_URL", "GALAXY_TOKEN", "KUBESPRAY_VERSION")
    if not os.getenv(name)
]
if missing_envs:
    logging.error("GALAXY_URL GALAXY_TOKEN and KUBESPRAY_VERSION")
    sys.exit(1)

VERSION = os.getenv("KUBESPRAY_VERSION")
BUILD_VERSION = f"v{VERSION}"
REPO_URL = os.getenv("KUBESPRAY_REPO", "https://github.com/kubernetes-sigs/kubespray.git")
GALAXY_TARGET = os.getenv("GALAXY_TARGET", "kubernetes_sigs_kubespray")

DATA_DIR = Path(os.getenv("DATA_DIR", "/data")).resolve()
build_dir = DATA_DIR / GALAXY_TARGET
temp_dir = DATA_DIR / "temp"


def run(command: list[str], cwd: Path | None = None) -> None:
    logging.info("Running: %s", " ".join(command))
    subprocess.run(command, check=True, cwd=str(cwd) if cwd else None)


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        logging.info("Removing %s", path)
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


logging.info("Cleaning and creating build/temp directories under %s", DATA_DIR)
ensure_clean_dir(build_dir)
ensure_clean_dir(temp_dir)

logging.info("Cloning kubespray repository: %s", REPO_URL)
run(["git", "clone", REPO_URL, str(temp_dir)])

logging.info("Checking out version %s", BUILD_VERSION)
run(["git", "checkout", BUILD_VERSION], cwd=temp_dir)

logging.info("Copying files from temp directory to build directory (excluding .git)")
run(["rsync", "-av", "--exclude", ".git", f"{temp_dir}/", f"{build_dir}/"])

python_cmd = sys.executable

logging.info("Running collection fixer scripts inside the container")
build_dir_str = str(build_dir)
run([python_cmd, "/app/fix_galaxy.py", build_dir_str, VERSION])
run([python_cmd, "/app/fix_docs.py", build_dir_str, VERSION])
run([python_cmd, "/app/fix_role_name.py", build_dir_str])
run([python_cmd, "/app/fix_role_meta.py", build_dir_str])
run([python_cmd, "/app/fix_role_readme.py", build_dir_str])
run([python_cmd, "/app/fix_playbooks.py", build_dir_str])
logging.info("Collection build completed successfully.")

logging.info("Publishing collection to Ansible Galaxy.")
run([python_cmd, "/app/push_to_galaxy.py", str(build_dir)])