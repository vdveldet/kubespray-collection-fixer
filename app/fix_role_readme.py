#!/usr/bin/env python3
"""
fix_role_readme.py

Adds README.md files to all roles that don't have one.
Galaxy requires each role to have a README file for collection imports to succeed.

Usage:
  python3 fix_role_readme.py /path/to/collection-root
  python3 fix_role_readme.py /path/to/collection-root --dry-run
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Tuple

try:
    import yaml
except ImportError:
    yaml = None


def require_pyyaml():
    if yaml is None:
        raise SystemExit("ERROR: PyYAML is required. Install it with: pip install pyyaml")


def find_roles(root: str) -> List[Tuple[str, str]]:
    """
    Find all role directories under root/roles.
    Returns list of (role_path, role_name) tuples.
    Includes regular roles, nested roles, and parent roles.
    """
    roles = []
    roles_dir = os.path.join(root, "roles")

    if not os.path.exists(roles_dir):
        return roles

    seen_roles = set()
    skip_dirs = {'meta', 'tasks', 'handlers', 'defaults', 'vars', 'files',
                 'templates', 'library', 'molecule', 'tests'}

    # Find all meta/main.yml files to identify roles
    for meta_file in Path(roles_dir).rglob("meta/main.yml"):
        # Role directory is parent of 'meta' directory
        role_path = meta_file.parent.parent
        role_name = role_path.name

        # Avoid duplicates
        role_path_str = str(role_path)
        if role_path_str not in seen_roles:
            seen_roles.add(role_path_str)
            roles.append((role_path_str, role_name))

    # Also find roles that have tasks but no meta
    for tasks_dir in Path(roles_dir).rglob("tasks"):
        if not tasks_dir.is_dir():
            continue

        role_path = tasks_dir.parent
        role_path_str = str(role_path)

        # Check if this is a valid role (not already added and is direct child or nested under roles/)
        if role_path_str not in seen_roles:
            # Ensure it has main.yml or main.yaml in tasks
            has_main = (tasks_dir / "main.yml").exists() or (tasks_dir / "main.yaml").exists()
            if has_main:
                role_name = role_path.name
                seen_roles.add(role_path_str)
                roles.append((role_path_str, role_name))

    # Find parent roles (directories with defaults/vars or containing sub-roles)
    for entry in Path(roles_dir).rglob("*"):
        if not entry.is_dir():
            continue

        if entry.name in skip_dirs:
            continue

        entry_str = str(entry)
        if entry_str in seen_roles:
            continue

        has_defaults = (entry / "defaults").exists()
        has_vars = (entry / "vars").exists()

        # Check for sub-roles
        has_subroles = False
        for item in entry.iterdir():
            if item.is_dir() and item.name not in skip_dirs:
                if (item / 'tasks').exists() or (item / 'meta').exists():
                    has_subroles = True
                    break

        if has_defaults or has_vars or has_subroles:
            seen_roles.add(entry_str)
            role_name = entry.name
            roles.append((entry_str, role_name))

    return sorted(roles, key=lambda x: x[0])


def get_role_description(role_path: str, role_name: str) -> str:
    """Get role description from meta/main.yml if available."""
    require_pyyaml()

    meta_file = os.path.join(role_path, "meta", "main.yml")

    if not os.path.exists(meta_file):
        return f"Kubespray role: {role_name}"

    try:
        with open(meta_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if isinstance(data, dict) and 'galaxy_info' in data:
            galaxy_info = data['galaxy_info']
            if isinstance(galaxy_info, dict) and 'description' in galaxy_info:
                return galaxy_info['description']
    except Exception:
        pass

    return f"Kubespray role: {role_name}"


def create_readme(role_path: str, role_name: str, dry_run: bool) -> bool:
    """Create a README.md file for a role."""
    readme_path = os.path.join(role_path, "README.md")

    # Check if README already exists
    if os.path.exists(readme_path):
        return False

    # Get description from meta/main.yml
    description = get_role_description(role_path, role_name)

    # Check if this is a parent role (contains sub-roles)
    skip_dirs = {'meta', 'defaults', 'vars', 'files', 'templates', 'handlers', 'tasks', 'molecule', 'tests'}
    sub_roles = []
    role_dir_path = Path(role_path)

    for item in role_dir_path.iterdir():
        if item.is_dir() and item.name not in skip_dirs:
            if (item / 'tasks').exists() or (item / 'meta').exists():
                sub_roles.append(item.name)

    sub_roles_text = ""
    if sub_roles:
        sub_roles_text = "\n\n## Sub-roles\n\nThis parent role contains the following sub-roles:\n\n"
        sub_roles_text += "\n".join([f"- `{sr}`" for sr in sorted(sub_roles)])

    # Generate README content
    readme_content = f"""# Ansible Role: {role_name}

{description}

## Description

This role is part of the [Kubespray](https://github.com/kubernetes-sigs/kubespray) project,
which provides Ansible playbooks to deploy a production-ready Kubernetes cluster.
{sub_roles_text}

## Requirements

See the main [Kubespray documentation](https://kubespray.io/) for requirements.

## Role Variables

See `defaults/main.yml` and `vars/main.yml` for available variables.

## Dependencies

See `meta/main.yml` for role dependencies.

## Example Playbook

This role is typically used as part of the Kubespray cluster deployment.
See the [Kubespray documentation](https://kubespray.io/) for usage examples.

## License

Apache License 2.0

## Author Information

This role is maintained by the Kubespray community.
For more information, visit: https://github.com/kubernetes-sigs/kubespray
"""

    if not dry_run:
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)

    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Add README.md to roles missing them")
    ap.add_argument("root", help="Root directory of the collection")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be created without writing")
    args = ap.parse_args()

    if yaml is None:
        print("WARNING: PyYAML not available. Role descriptions will be generic.", file=sys.stderr)

    root = os.path.abspath(args.root)

    if not os.path.exists(root):
        print(f"ERROR: Root directory not found: {root}", file=sys.stderr)
        return 1

    # Find all roles
    roles = find_roles(root)

    if not roles:
        print(f"No roles found in: {root}")
        return 0

    print(f"Found {len(roles)} roles\n")

    if args.dry_run:
        print("[DRY-RUN] Would create the following README files:\n")

    created_count = 0
    for role_path, role_name in roles:
        if create_readme(role_path, role_name, args.dry_run):
            created_count += 1
            readme_path = os.path.join(role_path, "README.md")
            print(f"{'[DRY-RUN] ' if args.dry_run else ''}[CREATED] {readme_path}")
        else:
            readme_path = os.path.join(role_path, "README.md")
            print(f"[OK] {readme_path} (already exists)")

    print(f"\n{'[DRY-RUN] ' if args.dry_run else ''}Done! Created {created_count} README files.")
    print(f"Total roles: {len(roles)}, Already had README: {len(roles) - created_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
