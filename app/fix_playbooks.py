#!/usr/bin/env python3
"""
fix_playbooks.py

Analyzes Ansible playbooks and adds documentation headers explaining what each playbook does.
Scans all .yml and .yaml files in the target directory and generates informative headers
based on the playbook content (tasks, roles, includes, etc.).
This is NOT take over by galaxy but is best pracice.

Usage:
  python3 fix_playbooks.py /path/to/directory
  python3 fix_playbooks.py /path/to/directory --dry-run
  python3 fix_playbooks.py /path/to/directory --no-backup
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple

try:
    import yaml
except ImportError:
    yaml = None


def require_pyyaml():
    if yaml is None:
        raise SystemExit("ERROR: PyYAML is required. Install it with: pip install pyyaml")


def find_playbooks(root: str) -> List[str]:
    """
    Find all playbook files (.yml, .yaml) in the current directory only.
    Returns list of absolute file paths.
    """
    playbooks = []
    root_path = Path(root)

    if not root_path.exists() or not root_path.is_dir():
        return playbooks

    try:
        # Iterate through files in the directory
        for item in root_path.iterdir():
            # Only process files (not directories)
            if not item.is_file():
                continue

            # Check if it has a .yml or .yaml extension
            if item.suffix not in ['.yml', '.yaml']:
                continue

            # Skip if filename suggests it's not a playbook
            if item.name.startswith('_'):
                continue

            playbooks.append(str(item))
    except Exception as e:
        print(f"Error reading directory: {e}")
        return playbooks

    return sorted(playbooks)


def parse_playbook(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse a YAML playbook file and return the content as a list of plays.
    """
    try:
        with open(file_path, 'r') as f:
            content = yaml.safe_load(f)
            if isinstance(content, list):
                return content if content else []
            elif isinstance(content, dict):
                return [content]
            else:
                return []
    except Exception as e:
        print(f"  WARNING: Failed to parse {file_path}: {e}")
        return []


def extract_playbook_info(plays: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract relevant information from playbook plays to generate documentation.
    """
    info = {
        'name': None,
        'hosts': [],
        'roles': [],
        'tasks': [],
        'imports': [],
        'includes': [],
        'handlers': [],
        'vars': {}
    }

    if not plays:
        return info

    for play in plays:
        if not isinstance(play, dict):
            continue

        # Get play name
        if 'name' in play and not info['name']:
            info['name'] = play['name']

        # Get hosts
        if 'hosts' in play:
            hosts = play['hosts']
            if isinstance(hosts, str):
                info['hosts'].append(hosts)
            elif isinstance(hosts, list):
                info['hosts'].extend(hosts)

        # Get roles
        if 'roles' in play:
            roles_list = play['roles']
            if isinstance(roles_list, list):
                for role in roles_list:
                    if isinstance(role, dict):
                        if 'role' in role:
                            info['roles'].append(role['role'])
                        elif 'name' in role:
                            info['roles'].append(role['name'])
                    elif isinstance(role, str):
                        info['roles'].append(role)

        # Get task names
        if 'tasks' in play:
            tasks_list = play['tasks']
            if isinstance(tasks_list, list):
                for task in tasks_list:
                    if isinstance(task, dict) and 'name' in task:
                        info['tasks'].append(task['name'])

        # Get imports and includes
        if 'import_playbook' in play:
            info['imports'].append(play['import_playbook'])
        if 'include' in play:
            info['includes'].append(play['include'])

        # Get handlers
        if 'handlers' in play:
            handlers_list = play['handlers']
            if isinstance(handlers_list, list):
                for handler in handlers_list:
                    if isinstance(handler, dict) and 'name' in handler:
                        info['handlers'].append(handler['name'])

        # Get variables
        if 'vars' in play and isinstance(play['vars'], dict):
            info['vars'].update(play['vars'])

    return info


def generate_header(file_path: str, info: Dict[str, Any]) -> str:
    """
    Generate a documentation header for the playbook.
    """
    header_lines = ['---', '# Playbook Documentation', '#']

    # Add playbook name
    file_name = Path(file_path).name
    if info['name']:
        header_lines.append(f"# Purpose: {info['name']}")
    else:
        header_lines.append(f"# File: {file_name}")

    header_lines.append('#')

    # Add details
    if info['hosts']:
        header_lines.append(f"# Target Hosts: {', '.join(set(info['hosts']))}")

    if info['roles']:
        header_lines.append(f"# Roles: {', '.join(set(info['roles']))}")

    if info['imports']:
        header_lines.append(f"# Imports: {', '.join(set(info['imports']))}")

    if info['includes']:
        header_lines.append(f"# Includes: {', '.join(set(info['includes']))}")

    if info['tasks']:
        # List first 3-5 key tasks
        key_tasks = info['tasks'][:5]
        header_lines.append(f"# Key Tasks:")
        for task in key_tasks:
            header_lines.append(f"#   - {task}")

    if info['handlers']:
        header_lines.append(f"# Handlers: {', '.join(set(info['handlers']))}")

    header_lines.append('#')

    return '\n'.join(header_lines) + '\n'


def has_documentation_header(file_content: str) -> bool:
    """
    Check if the playbook already has a documentation header.
    """
    lines = file_content.split('\n', 10)
    for line in lines[:10]:
        if 'Playbook Documentation' in line or '# Purpose:' in line:
            return True
    return False


def add_playbook_documentation(file_path: str, dry_run: bool = False, no_backup: bool = False) -> Tuple[bool, str]:
    """
    Add documentation header to a playbook file.
    Returns (modified, message) tuple.
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Check if already documented
        if has_documentation_header(content):
            return False, f"Already documented"

        # Parse playbook
        plays = parse_playbook(file_path)
        if not plays:
            return False, f"No valid plays found"

        # Extract info
        info = extract_playbook_info(plays)

        # Generate header
        header = generate_header(file_path, info)

        # Check if content starts with YAML separator
        if content.startswith('---'):
            # Remove the first --- so we don't duplicate it
            content_without_sep = content[3:].lstrip('\n')
            new_content = header + content_without_sep
        else:
            new_content = header + content

        if dry_run:
            return True, f"Would add documentation header"

        # Create backup if requested
        if not no_backup:
            backup_path = file_path + '.bak'
            with open(backup_path, 'w') as f:
                f.write(content)

        # Write updated content
        with open(file_path, 'w') as f:
            f.write(new_content)

        return True, f"Added documentation header"

    except Exception as e:
        return False, f"Error: {e}"


def main():
    parser = argparse.ArgumentParser(
        description='Add documentation headers to Ansible playbooks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python3 fix_playbooks.py /path/to/playbooks
  python3 fix_playbooks.py /path/to/playbooks --dry-run
  python3 fix_playbooks.py /path/to/playbooks --no-backup
        '''
    )
    parser.add_argument('root', help='Root directory containing playbooks')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without modifying files')
    parser.add_argument('--no-backup', action='store_true',
                       help='Do not create .bak backup files')

    args = parser.parse_args()

    require_pyyaml()

    # Validate root directory
    if not os.path.isdir(args.root):
        print(f"ERROR: {args.root} is not a valid directory")
        sys.exit(1)

    # Find playbooks
    playbook_dir = os.path.join(args.root,"playbooks")
    playbooks = find_playbooks(playbook_dir)

    if not playbooks:
        print("No playbooks found")
        sys.exit(0)

    print(f"Found {len(playbooks)} playbook(s)")
    print()

    modified_count = 0
    skipped_count = 0

    # Process each playbook
    for playbook in playbooks:
        rel_path = os.path.relpath(playbook, args.root)
        modified, message = add_playbook_documentation(
            playbook,
            dry_run=args.dry_run,
            no_backup=args.no_backup
        )

        if modified:
            print(f"✓ {rel_path}: {message}")
            modified_count += 1
        else:
            print(f"- {rel_path}: {message}")
            skipped_count += 1

    print()
    print(f"Summary:")
    print(f"  Modified: {modified_count}")
    print(f"  Skipped: {skipped_count}")

    if args.dry_run:
        print()
        print("DRY-RUN: No files were modified")


if __name__ == '__main__':
    main()
