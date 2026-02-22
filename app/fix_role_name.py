#!/usr/bin/env python3
"""
fix_role_name.py

Fixes invalid Ansible role names to be Galaxy-compliant.

Galaxy role naming requirements:
- Only lowercase letters, numbers, and underscores
- Cannot start with a number
- No hyphens (must use underscores)
- Must be between 2 and 55 characters

This script will:
1. Find all roles with invalid names
2. Rename role directories (hyphens -> underscores, lowercase)
3. Update references in meta/main.yml dependencies
4. Update references in playbooks

Usage:
  python3 fix_role_name.py /path/to/collection-root
  python3 fix_role_name.py /path/to/collection-root --dry-run
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import yaml
except ImportError:
    yaml = None


def require_pyyaml():
    if yaml is None:
        raise SystemExit("ERROR: PyYAML is required. Install it with: pip install pyyaml")


def is_valid_role_name(name: str) -> bool:
    """Check if a role name is Galaxy-compliant."""
    # Must be 2-55 characters
    if not (2 <= len(name) <= 55):
        return False
    # Only lowercase alphanumeric and underscores
    if not re.match(r'^[a-z0-9_]+$', name):
        return False
    # Cannot start with a number
    if name[0].isdigit():
        return False
    return True


def fix_role_name(name: str) -> str:
    """Convert invalid role name to valid one."""
    # Convert to lowercase
    fixed = name.lower()
    # Replace hyphens with underscores
    fixed = fixed.replace('-', '_')
    # Remove any invalid characters
    fixed = re.sub(r'[^a-z0-9_]', '', fixed)
    # Ensure it doesn't start with a number
    if fixed and fixed[0].isdigit():
        fixed = 'role_' + fixed
    # Ensure minimum length
    if len(fixed) < 2:
        fixed = 'role_' + fixed
    # Truncate if too long
    if len(fixed) > 55:
        fixed = fixed[:55]
    return fixed


def find_roles(root: str) -> List[Tuple[str, str]]:
    """
    Recursively find all role directories under root/roles.
    
    A role is a directory that contains either:
    - A meta/ subdirectory
    - A tasks/ subdirectory
    
    Returns list of (role_path, role_name) tuples, sorted by depth (deepest first)
    to ensure parent roles are renamed after child roles.
    """
    roles = []
    roles_dir = os.path.join(root, "roles")

    if not os.path.exists(roles_dir):
        return roles

    # Recursively search for role directories
    def search_for_roles(search_path: Path, base_path: Path):
        """Recursively search for role directories, continuing even after finding roles."""
        try:
            for entry in search_path.iterdir():
                if not entry.is_dir():
                    continue

                # Check if this directory is a role (has meta or tasks subdirs)
                has_meta = (entry / "meta").exists()
                has_tasks = (entry / "tasks").exists()

                if has_meta or has_tasks:
                    # Found a role - record it
                    role_name = entry.name
                    path_depth = len(entry.relative_to(base_path).parts)
                    roles.append((str(entry), role_name, path_depth))
                    # Continue searching inside this role for nested roles
                    search_for_roles(entry, base_path)
                else:
                    # Not a role, but might contain nested roles - recurse
                    search_for_roles(entry, base_path)
        except (PermissionError, OSError):
            # Skip directories we can't read
            pass

    search_for_roles(Path(roles_dir), Path(roles_dir))

    # Sort by depth (deepest first) to avoid path invalidation when renaming parents
    roles.sort(key=lambda x: x[2], reverse=True)

    return [(path, name) for path, name, _ in roles]


def update_yaml_file(file_path: str, old_name: str, new_name: str, dry_run: bool, rename_map: Dict[str, str] = None) -> bool:
    """Update role references in a YAML file."""
    require_pyyaml()

    if rename_map is None:
        rename_map = {}

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if old name is referenced
        if old_name not in content:
            return False

        # Skip Kubernetes manifests and other non-Ansible files
        # These typically have apiVersion or kind at the top level
        if any(keyword in content[:500] for keyword in ['apiVersion:', 'kind: ', 'metadata:']):
            return False

        # Try to load and update YAML
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError:
            # If YAML parsing fails (e.g., multi-document), skip this file
            return False

        modified = False

        # Helper function to update role references in various formats
        def update_role_reference(role_ref: str) -> str:
            """Update a role reference to use new names."""
            result = role_ref
            
            # First, update any parent namespace/directory names in the reference
            # Handle patterns like: namespace/role or namespace-name/role-name
            if '/' in result:
                parts = result.split('/')
                # Update each part if it's in the rename map
                for i, part in enumerate(parts):
                    if part in rename_map:
                        parts[i] = rename_map[part]
                result = '/'.join(parts)
                
                # Also check if the role name part (last part) needs updating
                # Handle the specific old_name we're looking for
                if parts[-1] == old_name:
                    parts[-1] = new_name
                    result = '/'.join(parts)
            else:
                # No slash - simple role name
                if result == old_name:
                    result = new_name
                # Also check dot-based namespaces
                elif result.endswith('.' + old_name):
                    result = result.replace('.' + old_name, '.' + new_name)
            
            return result

        # Update dependencies in meta/main.yml
        if isinstance(data, dict) and 'dependencies' in data:
            deps = data['dependencies']
            if isinstance(deps, list):
                for i, dep in enumerate(deps):
                    if isinstance(dep, dict) and 'role' in dep:
                        role_ref = dep['role']
                        new_ref = update_role_reference(role_ref)
                        if new_ref != role_ref:
                            deps[i]['role'] = new_ref
                            modified = True
                    elif isinstance(dep, str):
                        new_ref = update_role_reference(dep)
                        if new_ref != dep:
                            deps[i] = new_ref
                            modified = True

        # Recursively update role references in the entire structure
        def update_structure(obj):
            """Recursively update role references in nested structures."""
            nonlocal modified
            
            if isinstance(obj, dict):
                # Handle role references in various fields
                for key in ['role', 'name']:
                    if key in obj:
                        value = obj[key]
                        if isinstance(value, str):
                            new_value = update_role_reference(value)
                            if new_value != value:
                                obj[key] = new_value
                                modified = True
                
                # Recursively process all nested structures
                for value in obj.values():
                    if isinstance(value, (dict, list)):
                        update_structure(value)
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    if isinstance(item, dict):
                        update_structure(item)
                    elif isinstance(item, str):
                        new_item = update_role_reference(item)
                        if new_item != item:
                            obj[i] = new_item
                            modified = True

        # Apply updates to the entire data structure
        update_structure(data)

        if modified and not dry_run:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('---\n')
                yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

        return modified

    except Exception as e:
        print(f"  [WARNING] Could not update {file_path}: {e}", file=sys.stderr)
        return False


def rename_role(role_path: str, old_name: str, new_name: str, dry_run: bool) -> bool:
    """Rename a role directory. Handle existing targets (directories or symlinks)."""
    parent_dir = os.path.dirname(role_path)
    new_path = os.path.join(parent_dir, new_name)

    if os.path.exists(new_path) or os.path.islink(new_path):
        # Check if target is a symlink
        if os.path.islink(new_path):
            print(f"  [INFO] Target is a symlink: {new_path}", file=sys.stderr)
            print(f"  [INFO] Replacing symlink with directory from: {role_path}", file=sys.stderr)

            if not dry_run:
                os.remove(new_path)  # Remove the symlink
                shutil.move(role_path, new_path)  # Move the actual directory

        # Target is a directory
        elif os.path.isdir(new_path):
            print(f"  [INFO] Target directory already exists: {new_path}", file=sys.stderr)
            print(f"  [INFO] Deleting duplicate source: {role_path}", file=sys.stderr)

            if not dry_run:
                shutil.rmtree(role_path)

        else:
            # Target is a file (shouldn't happen, but handle it)
            print(f"  [ERROR] Target exists as a file: {new_path}", file=sys.stderr)
            return False

        return True

    if not dry_run:
        shutil.move(role_path, new_path)

    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Fix invalid Ansible role names")
    ap.add_argument("root", help="Root directory of the collection")
    ap.add_argument("--dry-run", action="store_true", help="Show what would change without modifying")
    args = ap.parse_args()

    require_pyyaml()

    root = os.path.abspath(args.root)

    if not os.path.exists(root):
        print(f"ERROR: Root directory not found: {root}", file=sys.stderr)
        return 1

    # Find all roles
    roles = find_roles(root)

    if not roles:
        print(f"No roles found in: {root}")
        return 0

    # Build rename mapping for role names
    rename_map: Dict[str, str] = {}
    for role_path, role_name in roles:
        if not is_valid_role_name(role_name):
            fixed_name = fix_role_name(role_name)
            rename_map[role_name] = fixed_name
            print(f"[INVALID] {role_name} -> {fixed_name}")

    # Also scan for invalid parent directory names in the roles directory
    # These might be used in namespace/role references in playbooks
    roles_dir = os.path.join(root, "roles")
    if os.path.exists(roles_dir):
        for entry in Path(roles_dir).iterdir():
            if entry.is_dir():
                dir_name = entry.name
                if not is_valid_role_name(dir_name):
                    fixed_name = fix_role_name(dir_name)
                    if dir_name not in rename_map:
                        rename_map[dir_name] = fixed_name
                        print(f"[INVALID-DIR] {dir_name} -> {fixed_name}")

    # Also scan YAML files for role references that use hyphens (invalid names)
    # and add the invalid names to the rename map
    playbook_files = list(Path(root).rglob("*.yml")) + list(Path(root).rglob("*.yaml"))
    for playbook in playbook_files:
        try:
            with open(str(playbook), 'r', encoding='utf-8') as f:
                content = f.read()
            # Look for role references with hyphens (which are invalid)
            # Patterns:
            # 1. role: namespace/role-name or role: role-name
            # 2. name: namespace/role-name when file contains import_role or include_role
            import re
            
            # Pattern for role: fields
            role_patterns = re.findall(r'role:\s+([a-z0-9_\-./]+)', content)
            
            # If file contains import_role or include_role, also look for name: fields
            # that appear in those blocks
            if 'import_role' in content or 'include_role' in content:
                # Look for name: patterns that are likely in import_role/include_role blocks
                # These are indented and followed by other role-related fields like tasks_from
                name_patterns = re.findall(r'name:\s+([a-z0-9_\-./]+)', content)
                role_patterns.extend(name_patterns)
            
            for role_ref in role_patterns:
                # Split by slash to get namespace and role name
                parts = role_ref.split('/')
                for part in parts:
                    if '-' in part and not is_valid_role_name(part):
                        fixed_part = fix_role_name(part)
                        if part not in rename_map:
                            rename_map[part] = fixed_part
                            print(f"[INVALID-REF] {part} -> {fixed_part}")
        except (PermissionError, OSError, UnicodeDecodeError):
            pass

    if not rename_map:
        print("\nAll role names are valid! No changes needed.")
        return 0

    print(f"\nFound {len(rename_map)} invalid names")

    if args.dry_run:
        print("\n[DRY-RUN] Would make the following changes:")

    # Rename role directories (deepest first to avoid path issues)
    print("\n--- Renaming role directories ---")
    renamed_paths = {}  # Track old_path -> new_path mappings

    for role_path, role_name in roles:
        if role_name in rename_map:
            new_name = rename_map[role_name]

            # Resolve the actual current path, accounting for parent directory renames
            current_path = role_path
            
            # Check if any parent directory has been renamed
            for old_path, new_path in renamed_paths.items():
                if current_path.startswith(old_path + os.sep):
                    # Replace the old parent path with the new one
                    current_path = new_path + current_path[len(old_path):]
                    break

            # Verify the path still exists
            if not os.path.exists(current_path):
                print(f"  [WARNING] Path no longer exists (likely renamed parent): {role_path}", file=sys.stderr)
                continue

            parent_dir = os.path.dirname(current_path)
            new_path = os.path.join(parent_dir, new_name)

            print(f"{'[DRY-RUN] ' if args.dry_run else ''}Renaming: {current_path} -> {new_name}")
            if rename_role(current_path, role_name, new_name, args.dry_run):
                # Track the rename: use the original path as key
                renamed_paths[role_path] = new_path
            else:
                print(f"  [ERROR] Failed to rename {current_path}", file=sys.stderr)

    # Update all meta/main.yml files for dependencies
    print("\n--- Updating role dependencies ---")
    meta_files = list(Path(root).rglob("meta/main.yml"))

    for meta_file in meta_files:
        meta_path = str(meta_file)
        for old_name, new_name in rename_map.items():
            if update_yaml_file(meta_path, old_name, new_name, args.dry_run, rename_map):
                print(f"{'[DRY-RUN] ' if args.dry_run else ''}Updated: {meta_path} ({old_name} -> {new_name})")

    # Update playbook files
    print("\n--- Updating playbooks ---")
    playbook_files = list(Path(root).rglob("*.yml")) + list(Path(root).rglob("*.yaml"))

    for playbook in playbook_files:
        playbook_path = str(playbook)

        # Skip meta files (already processed)
        if "meta/main.yml" in playbook_path:
            continue

        # Skip common non-Ansible directories
        skip_dirs = ['/tests/', '/files/', '/templates/', '/library/']
        if any(skip_dir in playbook_path for skip_dir in skip_dirs):
            continue

        for old_name, new_name in rename_map.items():
            if update_yaml_file(playbook_path, old_name, new_name, args.dry_run, rename_map):
                print(f"{'[DRY-RUN] ' if args.dry_run else ''}Updated: {playbook_path} ({old_name} -> {new_name})")

    # Final cleanup: Remove any remaining directories with hyphens in roles/
    print("\n--- Final cleanup: Removing remaining invalid directories ---")
    roles_dir = os.path.join(root, "roles")
    if os.path.exists(roles_dir):
        removed_count = 0
        for entry in Path(roles_dir).iterdir():
            if entry.is_dir() and '-' in entry.name:
                # Check if valid version exists
                valid_name = entry.name.replace('-', '_')
                valid_path = entry.parent / valid_name

                if valid_path.exists():
                    print(f"{'[DRY-RUN] ' if args.dry_run else ''}Removing invalid directory: {entry.name} (valid version exists: {valid_name})")
                    if not args.dry_run:
                        shutil.rmtree(entry)
                    removed_count += 1

        if removed_count > 0:
            print(f"{'[DRY-RUN] Would remove' if args.dry_run else 'Removed'} {removed_count} invalid directories")

    print(f"\n{'[DRY-RUN] ' if args.dry_run else ''}Done! Fixed {len(rename_map)} role names.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
