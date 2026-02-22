#!/usr/bin/env python3
"""
This script will ensure the galaxy.yml file is always correctly formatted.
It writes a fixed galaxy.yml configuration to the collection directory.
"""

import os
import sys

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
GALAXY_TEMPLATE_PATH = os.path.join(TEMPLATES_DIR, "galaxy.yml.j2")
GALAXY_TARGET = os.getenv("GALAXY_TARGET", "kubernetes_sigs_kubespray")


def load_template(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def split_galaxy_target(target):
    dash_idx = target.rfind("-")
    underscore_idx = target.rfind("_")
    split_idx = max(dash_idx, underscore_idx)
    if split_idx <= 0 or split_idx == len(target) - 1:
        raise ValueError("GALAXY_TARGET must contain '-' or '_' separating namespace and name")
    return target[:split_idx], target[split_idx + 1:]

def get_galaxy_yml_content(version):
    """Generate galaxy.yml content with the specified version."""
    namespace, name = split_galaxy_target(GALAXY_TARGET)
    template = load_template(GALAXY_TEMPLATE_PATH)
    return template.format(version=version, namespace=namespace, name=name)


def main():
    # Get the collection directory and version from command-line arguments
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <collection_directory> <version>")
        print(f"Example: {sys.argv[0]} /path/to/collection 0.0.12")
        return 1
    
    collection_dir = sys.argv[1]
    version = sys.argv[2]

    galaxy_yml_path = os.path.join(collection_dir, "galaxy.yml")

    if not os.path.exists(collection_dir):
        print(f"ERROR: Collection directory not found: {collection_dir}")
        return 1

    # Write the galaxy.yml file
    galaxy_yml_content = get_galaxy_yml_content(version)
    with open(galaxy_yml_path, 'w', encoding='utf-8') as f:
        f.write(galaxy_yml_content.lstrip())

    print(f"Successfully wrote galaxy.yml to: {galaxy_yml_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
