#!/usr/bin/env python3
"""Execute explicitly supplied argv, preserving actual run evidence. No shell or recorded-command replay."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from project_io import atomic_json, digest, encoded, load, local, now, state, write_new_tree


def run(root, spec, command, timeout=None):
    root = Path(root).resolve()
    current = state(root)
    if current.get('schema_version') != 2:
        raise ValueError('Migrate project state to schema 2 before recording runs')
    identity = spec.get('id', '')
    if not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', identity):
        raise ValueError('Use a stable run ID containing letters/digits/._-')
    if any(r.get('id') == identity for r in current['runs']):
        raise ValueError('Run ID already exists; use a new ID')
    if not command or any(not isinstance(arg, str) for arg in command):
        raise ValueError('Explicit command argv is required')
    if timeout is not None and timeout <= 0:
        raise ValueError('Timeout must be positive')
    for key in ('purpose', 'cache_policy'):
        if not isinstance(spec.get(key), str) or not spec[key].strip() or '待' in spec[key]:
            raise ValueError(f'Fill actual {key}')
    if type(spec.get('environment_rebuilt')) is not bool:
        raise ValueError('Declare environment_rebuilt as true/false')
    inputs = spec.get('inputs')
    if not isinstance(inputs, list) or not inputs:
        raise ValueError('Provide versioned actual inputs (a data manifest may represent external data)')
    artifacts = {r['id']: r for r in current['artifacts']}
    input_hashes = {}
    for ref in inputs:
        if not isinstance(ref, dict) or ref.get('id') not in artifacts:
            raise ValueError('Unknown run input')
        artifact = artifacts[ref['id']]
        if artifact['version'] != ref.get('version') or artifact['status'] == 'stale' or artifact.get('lifecycle') == 'retired':
            raise ValueError('Run input version is stale')
        input_hashes[ref['id']] = digest(local(root, artifact['path'], True))
    code = spec.get('code')
    if not isinstance(code, list) or not code or len(set(code)) != len(code):
        raise ValueError('List the actual code files; duplicate files are not allowed')
    source_files = [('code', rel) for rel in code] + [('config', spec.get('config')), ('environment', spec.get('environment'))]
    resolved = [(role, rel, local(root, rel, True)) for role, rel in source_files]
    output_paths = spec.get('outputs')
    if not isinstance(output_paths, list) or not output_paths or len(set(output_paths)) != len(output_paths):
        raise ValueError('Declare unique new output file paths')
    outputs = [local(root, rel) for rel in output_paths]
    if any(path.exists() for path in outputs):
        raise ValueError('Run outputs must be new files; use an isolated output location')
    run_base = current.get('layout', {}).get('runs', 'runs') + '/' + identity
    if local(root, run_base).exists():
        raise ValueError('Run directory already exists')
    snapshots, files = [], {}
    for number, (role, relative, file) in enumerate(resolved):
        snapshot = f'{run_base}/snapshots/{number:03d}-{file.name}'
        snapshots.append({'role': role, 'source': relative, 'snapshot': snapshot, 'sha256': digest(file)})
    task = spec.get('task')
    if task is not None and task not in {t.get('id') for t in current.get('tasks', []) if isinstance(t, dict)}:
        raise ValueError('Unknown task for this run; register the task first')
    record = {'id': identity, 'status': 'running', 'purpose': spec['purpose'], 'started_at': now(),
              **({'task': task} if task is not None else {}),
              'ended_at': None, 'returncode': None, 'cwd': '.', 'command': command,
              'inputs': inputs, 'input_hashes': input_hashes, 'snapshots': snapshots,
              'environment_rebuilt': spec['environment_rebuilt'], 'cache_policy': spec['cache_policy'],
              'stdout': f'{run_base}/stdout.log', 'stderr': f'{run_base}/stderr.log',
              'outputs': [], 'integrity_issues': []}
    record_path = f'{run_base}/run.json'
    files[record_path] = encoded(record)
    files[record['stdout']] = ''
    files[record['stderr']] = ''
    if any(path == local(root, run_base) or local(root, run_base) in path.parents for path in outputs):
        raise ValueError('Outputs must be outside the reserved run evidence directory')
    write_new_tree(root, files)
    current['runs'].append({'id': identity, 'status': 'running', 'path': record_path})
    atomic_json(root, '_pm/project-state.json', current)
    # The caller authorizes this concrete argv; never execute argv from project records.
    try:
        for snap, (_, _, source) in zip(snapshots, resolved):
            destination = local(root, snap['snapshot'])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            if digest(destination) != snap['sha256']:
                raise ValueError('Source changed while being snapshotted; incomplete run retained')
        with local(root, record['stdout']).open('w', encoding='utf-8') as stdout, local(root, record['stderr']).open('w', encoding='utf-8') as stderr:
            result = subprocess.run(command, cwd=root, shell=False, stdin=subprocess.DEVNULL,
                                    stdout=stdout, stderr=stderr, timeout=timeout, check=False)
        record['returncode'] = result.returncode
        record['status'] = 'succeeded' if result.returncode == 0 else 'failed'
    except subprocess.TimeoutExpired:
        record['status'] = 'timed_out'
    except KeyboardInterrupt:
        record['status'] = 'interrupted'
    except (OSError, ValueError) as error:
        record['status'] = 'failed'
        record['error'] = str(error)
    finally:
        record['ended_at'] = now()
        def changed(relative, expected, label):
            try:
                if digest(local(root, relative, True)) == expected:
                    return
            except (OSError, ValueError, RuntimeError):
                pass
            record['integrity_issues'].append(label + relative)
        for ref in inputs:
            changed(artifacts[ref['id']]['path'], input_hashes[ref['id']], 'Input missing/changed during execution: ')
        for snap in snapshots:
            changed(snap['source'], snap['sha256'], 'Source missing/changed during execution: ')
        for relative in output_paths:
            try:
                path = local(root, relative, True)
                record['outputs'].append({'path': relative, 'sha256': digest(path)})
            except (OSError, ValueError, RuntimeError):
                record['integrity_issues'].append('Missing/invalid output: ' + relative)
        if record['integrity_issues'] and record['status'] == 'succeeded':
            record['status'] = 'failed'
        atomic_json(root, record_path, record)
        latest = state(root)
        for row in latest['runs']:
            if row['id'] == identity:
                row['status'] = record['status']
        atomic_json(root, '_pm/project-state.json', latest)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--spec', required=True, help='Project-relative run specification')
    parser.add_argument('--timeout', type=float)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        command = args.command[1:] if args.command[:1] == ['--'] else args.command
        result = run(args.project, load(local(args.project, args.spec, True)), command, args.timeout)
        print(encoded({'ok': result['status'] == 'succeeded', 'run': result}))
        return 0 if result['status'] == 'succeeded' else 1
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(encoded({'ok': False, 'error': str(error)}))
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
