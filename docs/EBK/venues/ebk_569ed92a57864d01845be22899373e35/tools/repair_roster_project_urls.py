"""Repair only duplicated, same-project prefixes in Roster image URLs.

The actual image must exist under the selected project. No network access,
slot reassignment, member deletion, permission changes or credential access.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import unquote, urlsplit, urlunsplit


def normalize_url(value: str, project_root: Path, repository_root: str,
                  public_base: str) -> str:
    base = urlsplit(public_base.rstrip('/'))
    parsed = urlsplit(value)
    if base.scheme not in ('https', 'http') or not base.netloc:
        raise ValueError('project.json publicBaseUrl is not an HTTP(S) URL')
    if (parsed.scheme.lower(), parsed.netloc.lower()) != (base.scheme.lower(), base.netloc.lower()):
        return value
    prefix = base.path.rstrip('/') + '/'
    if not parsed.path.startswith(prefix):
        return value
    relative = parsed.path[len(prefix):]
    repeated = repository_root.strip('/') + '/'
    if not relative.startswith(repeated):
        return value
    # Remove only an exact repetition of THIS project's repository path.
    while relative.startswith(repeated):
        relative = relative[len(repeated):]
    decoded = unquote(relative)
    parts = decoded.split('/')
    if not decoded or decoded.startswith('/') or '\\' in decoded or any(p in ('.', '..') for p in parts):
        raise ValueError('Duplicated Roster URL has an unsafe relative path')
    root = project_root.resolve()
    target = (root / decoded).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise ValueError('Duplicated Roster URL has no matching image in this project: ' + decoded)
    return urlunsplit((parsed.scheme, parsed.netloc, prefix + relative, parsed.query, parsed.fragment))


def repair(root: Path) -> int:
    metadata = json.loads((root / 'project.json').read_text(encoding='utf-8-sig'))
    repository_root = str(metadata.get('root', '')).strip('/')
    public_base = str(metadata.get('publicBaseUrl', '')).strip()
    if not repository_root or not public_base:
        raise ValueError('project.json requires root and publicBaseUrl; existing data was not changed')
    if not root.resolve().as_posix().endswith('/' + repository_root):
        raise ValueError('Selected root does not match project.json; existing data was not changed')
    path = root / 'data' / 'roster_manifest.json'
    original = path.read_bytes()
    if len(original) > 16 * 1024 * 1024:
        raise ValueError('Roster exceeds the repair inspection limit; existing data was not changed')
    text = original.decode('utf-8-sig')
    replacements: dict[str, str] = {}

    def visit(value):
        if isinstance(value, dict):
            return {key: visit(item) for key, item in value.items()}
        if isinstance(value, list):
            return [visit(item) for item in value]
        if isinstance(value, str):
            fixed = normalize_url(value, root, repository_root, public_base)
            if fixed != value:
                replacements[value] = fixed
            return fixed
        return value

    expected = visit(json.loads(text))
    if not replacements:
        return 0
    # Preserve unrelated whitespace, ordering, values and escaping byte-for-byte.
    def replace_token(match):
        token = match.group(0)
        value = json.loads(token)
        return json.dumps(replacements[value], ensure_ascii=False) if value in replacements else token

    updated = re.sub(r'"(?:\\.|[^"\\])*"', replace_token, text)
    if json.loads(updated) != expected:
        raise ValueError('Unexpected non-value change; existing data was not changed')
    payload = (b'\xef\xbb\xbf' if original.startswith(b'\xef\xbb\xbf') else b'') + updated.encode('utf-8')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.ebk-roster-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if path.read_bytes() != original:
            raise ValueError('Roster changed during inspection; repair was not applied')
        os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return len(replacements)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    try:
        count = repair(args.root)
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(1, 'EBK Roster URL repair stopped: ' + str(exc) + '\n')
    print('EBK Roster URL repair: ' + str(count) + ' duplicated same-project URL(s) corrected')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
