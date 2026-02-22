#!/usr/bin/env python3
"""
fix_role_meta.py

Fixes Ansible role meta/main.yml files so Galaxy/Automation Hub imports won't crash
on missing/invalid metadata (galaxy_info.description).

It searches for: <root>/**/roles/*/meta/main.yml

Usage:
  python3 fix_role_meta.py /path/to/collection-source
  python3 fix_role_meta.py /path/to/collection-source --dry-run
  python3 fix_role_meta.py /path/to/collection-source --description-template "Role {role} from my collection"
  python3 fix_role_meta.py /path/to/collection-source --min-ansible-version 2.14
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import os
import shutil
import sys
from typing import Any, Dict, Tuple

try:
    import yaml  # PyYAML
except ImportError:
    yaml = None


def require_pyyaml() -> None:
    if yaml is None:
        raise SystemExit("ERROR: PyYAML is required. Install it with: pip install pyyaml")


def utc_stamp() -> str:
    return dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def role_name_from_meta_path(meta_path: str) -> str:
    # .../roles/<role>/meta/main.yml or .../roles/category/<role>/meta/main.yml
    # The role name is the parent directory of the 'meta' directory
    return os.path.basename(os.path.dirname(os.path.dirname(meta_path)))


def safe_load(text: str) -> Any:
    require_pyyaml()
    return yaml.safe_load(text)


def safe_dump(data: Any) -> str:
    require_pyyaml()
    return yaml.safe_dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )


def ensure_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def fix_meta_file(
    path: str,
    description_template: str,
    min_ansible_version: str | None,
    dry_run: bool,
    make_backup: bool,
) -> Tuple[bool, str]:
    role = role_name_from_meta_path(path)
    desired_desc = description_template.format(role=role).strip()

    existed = os.path.exists(path)
    original_text = ""
    if existed:
        with open(path, "r", encoding="utf-8") as f:
            original_text = f.read()

    changed = False
    reasons = []

    # Load/normalize YAML
    if (not existed) or (not original_text.strip()):
        data: Any = {}
        changed = True
        reasons.append("created" if not existed else "rewrote empty")
    else:
        try:
            data = safe_load(original_text)
            if data is None or not isinstance(data, dict):
                data = {}
                changed = True
                reasons.append("rewrote non-mapping")
        except Exception as e:
            data = {}
            changed = True
            reasons.append(f"rewrote invalid YAML ({e.__class__.__name__})")

    data = ensure_dict(data)

    # Ensure galaxy_info + description
    gi = data.get("galaxy_info")
    if not isinstance(gi, dict):
        gi = {}
        data["galaxy_info"] = gi
        changed = True
        reasons.append("added galaxy_info")

    desc = gi.get("description")
    if not isinstance(desc, str) or not desc.strip():
        gi["description"] = desired_desc
        changed = True
        reasons.append("set description")

    # Ensure standalone is set to false for collection roles
    if "standalone" not in gi:
        gi["standalone"] = False
        changed = True
        reasons.append("set standalone: false")

    if min_ansible_version:
        mav = gi.get("min_ansible_version")
        if not isinstance(mav, str) or not mav.strip():
            gi["min_ansible_version"] = min_ansible_version
            changed = True
            reasons.append("set min_ansible_version")

    # Ensure dependencies key exists
    if "dependencies" not in data or data.get("dependencies") is None:
        data["dependencies"] = []
        changed = True
        reasons.append("set dependencies []")

    if not changed:
        return False, "ok"

    new_text = "---\n" + safe_dump(data)

    if dry_run:
        return True, "DRY-RUN: " + "; ".join(reasons)

    os.makedirs(os.path.dirname(path), exist_ok=True)

    if existed and make_backup:
        backup = f"{path}.bak.{utc_stamp()}"
        shutil.copy2(path, backup)

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)

    return True, "; ".join(reasons)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="Root directory of the collection/source tree to scan")
    ap.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    ap.add_argument(
        "--description-template",
        default="Role {role} (auto-fixed for Galaxy import)",
        help="Template for galaxy_info.description. Use {role} placeholder.",
    )
    ap.add_argument(
        "--min-ansible-version",
        default=None,
        help="If set, adds galaxy_info.min_ansible_version when missing (e.g. 2.14).",
    )
    ap.add_argument("--no-backup", action="store_true", help="Do not create .bak backups")
    args = ap.parse_args()

    require_pyyaml()

    root = os.path.abspath(args.root)

    # Find existing meta/main.yml files
    pattern = os.path.join(root, "**", "roles", "**", "meta", "main.yml")
    files = sorted(glob.glob(pattern, recursive=True))

    # Also find roles that have tasks but no meta/main.yml
    # AND parent roles (directories with defaults/vars or containing sub-roles)
    roles_dir = os.path.join(root, "roles")
    if os.path.exists(roles_dir):
        from pathlib import Path

        skip_dirs = {'meta', 'tasks', 'handlers', 'defaults', 'vars', 'files',
                     'templates', 'library', 'molecule', 'tests'}

        # Find all tasks directories
        for tasks_dir in Path(roles_dir).rglob("tasks"):
            if not tasks_dir.is_dir():
                continue

            # Check if this role has main.yml or main.yaml
            has_main = (tasks_dir / "main.yml").exists() or (tasks_dir / "main.yaml").exists()
            if not has_main:
                continue

            # Role directory is parent of tasks
            role_dir = tasks_dir.parent
            meta_path = role_dir / "meta" / "main.yml"

            # Add to list if meta/main.yml doesn't exist
            if not meta_path.exists():
                files.append(str(meta_path))

        # Find parent roles (directories with defaults/vars or containing sub-roles)
        for entry in Path(roles_dir).rglob("*"):
            if not entry.is_dir():
                continue

            if entry.name in skip_dirs:
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
                meta_path = entry / "meta" / "main.yml"
                if not meta_path.exists():
                    files.append(str(meta_path))

        files = sorted(set(files))  # Remove duplicates and sort

    if not files:
        print(f"No role meta files found in: {root}")
        return 2

    changed_count = 0
    for p in files:
        try:
            changed, msg = fix_meta_file(
                p,
                description_template=args.description_template,
                min_ansible_version=args.min_ansible_version,
                dry_run=args.dry_run,
                make_backup=not args.no_backup,
            )
            if changed:
                changed_count += 1
                print(f"[CHANGED] {p} -> {msg}")
            else:
                print(f"[OK]      {p}")
        except Exception as e:
            print(f"[ERROR]   {p}: {e}", file=sys.stderr)

    print(f"\nDone. Files scanned: {len(files)}; changed: {changed_count}; dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

