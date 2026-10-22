"""Shared project-local paths, hashing and transactional generated files (stdlib)."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import tempfile


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def local(root, relative, must_exist=False):
    root = Path(root).resolve()
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError('Expected a nonempty project-relative path')
    win = PureWindowsPath(relative)
    if Path(relative).is_absolute() or win.drive or win.root or '..' in win.parts or '\\' in relative or ':' in relative or '\x00' in relative:
        raise ValueError(f'Use a project-relative path with forward slashes: {relative}')
    candidate = root / relative
    if not candidate.resolve().is_relative_to(root):
        raise ValueError(f'Path escapes project: {relative}')
    cursor = candidate
    while cursor != root:
        if cursor.is_symlink() or getattr(cursor, 'is_junction', lambda: False)():
            raise ValueError(f'Linked path is not allowed here: {relative}')
        cursor = cursor.parent
    if must_exist and not candidate.is_file():
        raise ValueError(f'Missing project file: {relative}')
    return candidate


def load(path):
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError(f'Expected JSON object: {path}')
    return value


def state(root):
    return load(local(root, '_pm/project-state.json', True))


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def write_new_tree(root, files):
    """Preflight all files; roll back this invocation only. Never replace existing files."""
    root = Path(root).resolve()
    plans = [(local(root, rel), content) for rel, content in files.items()]
    for path, _ in plans:
        if path.exists():
            raise ValueError(f'Refusing to replace existing file: {path}')
    made, directories = [], []
    try:
        for path, content in plans:
            missing, parent = [], path.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for directory in reversed(missing):
                directory.mkdir()
                directories.append(directory)
            local(root, path.relative_to(root).as_posix())
            with path.open('x', encoding='utf-8', newline='\n') as output:
                made.append(path)
                output.write(content)
    except Exception:
        for path in reversed(made):
            path.unlink(missing_ok=True)
        for path in reversed(directories):
            try:
                path.rmdir()
            except OSError:
                pass
        raise


def atomic_json(root, relative, value):
    """Replace one explicitly managed JSON file; no record is silently merged."""
    target = local(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(prefix='.blueprint-', dir=target.parent)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8', newline='\n') as output:
            output.write(encoded(value))
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
