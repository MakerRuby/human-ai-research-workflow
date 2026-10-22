#!/usr/bin/env python3
"""Compare declared fresh-run outputs; record scope and evidence, never infer scientific validity."""
import argparse
import json
import math
from pathlib import Path
import re
import sys

from project_io import atomic_json, digest, encoded, load, local, now, state, write_new_tree


def numeric_equal(expected, actual, atol, rtol):
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(expected) is type(actual) and expected == actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isfinite(expected) and math.isfinite(actual) and abs(expected - actual) <= atol + rtol * abs(expected)
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, dict):
        return expected.keys() == actual.keys() and all(numeric_equal(expected[k], actual[k], atol, rtol) for k in expected)
    if isinstance(expected, list):
        return len(expected) == len(actual) and all(numeric_equal(e, a, atol, rtol) for e, a in zip(expected, actual))
    return expected == actual


def verify(root, spec):
    root = Path(root).resolve()
    current = state(root)
    identity = spec.get('id', '')
    if not isinstance(identity, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', identity):
        raise ValueError('Invalid reproduction ID')
    if any(row.get('id') == identity for row in current.get('reproductions', [])):
        raise ValueError('Use a new reproduction ID; historical comparisons are preserved')
    for key in ('title', 'by', 'rationale'):
        if not isinstance(spec.get(key), str) or not spec[key].strip():
            raise ValueError(f'Missing {key}')
    if spec.get('scope') not in {'full', 'partial', 'smoke'} or type(spec.get('required')) is not bool:
        raise ValueError('Declare scope (full/partial/smoke) and required boolean')
    if current.get('schema_version') != 2:
        raise ValueError('Schema 2 is required')
    indexed = next((row for row in current['runs'] if row['id'] == spec.get('run')), None)
    if indexed is None or indexed['status'] != 'succeeded':
        raise ValueError('Comparison requires an indexed successful actual run')
    run_file = local(root, indexed['path'], True)
    run = load(run_file)
    if run.get('status') != 'succeeded' or run.get('returncode') != 0 or run.get('integrity_issues'):
        raise ValueError('Actual run is incomplete or failed')
    artifacts = {row['id']: row for row in current['artifacts']}
    refs = spec.get('inputs')
    if not isinstance(refs, list) or not refs:
        raise ValueError('Declare versioned inputs covering run inputs and expected result artifacts')
    hashes = {}
    for ref in refs:
        if not isinstance(ref, dict) or ref.get('id') not in artifacts:
            raise ValueError('Unknown reproduction input')
        artifact = artifacts[ref['id']]
        if artifact['version'] != ref.get('version') or artifact['status'] == 'stale' or artifact.get('lifecycle') == 'retired':
            raise ValueError('Reproduction input is stale')
        hashes[ref['id']] = digest(local(root, artifact['path'], True))
    if not {(r['id'], r['version']) for r in run['inputs']}.issubset({(r['id'], r['version']) for r in refs}):
        raise ValueError('Reproduction omits actual run inputs')
    if any(hashes.get(identity) != value for identity, value in run['input_hashes'].items()):
        raise ValueError('Run input changed since execution')
    for snap in run['snapshots']:
        if digest(local(root, snap['snapshot'], True)) != snap['sha256'] or digest(local(root, snap['source'], True)) != snap['sha256']:
            raise ValueError('Actual code/config/environment differs from run snapshots')
    comparisons = spec.get('comparisons')
    if not isinstance(comparisons, list) or not comparisons:
        raise ValueError('At least one explicit comparison is required')
    actual_outputs = {row['path']: row['sha256'] for row in run['outputs']}
    results = []
    for comparison in comparisons:
        if not isinstance(comparison, dict):
            raise ValueError('Invalid comparison')
        expected = local(root, comparison.get('expected'), True)
        actual = local(root, comparison.get('actual'), True)
        if expected.resolve() == actual.resolve() or (expected.exists() and actual.exists() and expected.samefile(actual)):
            raise ValueError('Expected and actual must be distinct files')
        if comparison['actual'] not in actual_outputs or digest(actual) != actual_outputs[comparison['actual']]:
            raise ValueError('Actual output was not produced by this run or was subsequently modified')
        if not any(artifacts[ref['id']]['path'] == comparison['expected'] for ref in refs):
            raise ValueError('Expected output must be a registered versioned reproduction input')
        mode = comparison.get('mode')
        result = {key: comparison[key] for key in ('expected', 'actual', 'mode')}
        if mode == 'sha256':
            passed = digest(expected) == digest(actual)
        elif mode == 'json_numeric':
            for key in ('atol', 'rtol'):
                value = comparison.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError('Provide finite nonnegative atol and rtol; no universal tolerance is assumed')
                result[key] = value
            passed = numeric_equal(json.loads(expected.read_text(encoding='utf-8-sig')),
                                   json.loads(actual.read_text(encoding='utf-8-sig')), result['atol'], result['rtol'])
        else:
            raise ValueError('Built-in modes: sha256 or json_numeric; use an evidence-linked professional check for other formats')
        result.update(status='pass' if passed else 'fail', expected_sha256=digest(expected), actual_sha256=digest(actual))
        results.append(result)
    status = 'pass' if all(row['status'] == 'pass' for row in results) else 'fail'
    report_path = (current.get('layout', {}).get('runs', 'runs') + '/' + run['id'] + '/' + identity + '.json')
    report = {'id': identity, 'status': status, 'run': run['id'], 'scope': spec['scope'], 'inputs': refs,
              'input_hashes': hashes, 'run_record_sha256': digest(run_file), 'results': results,
              'verified_at': now(), 'by': spec['by'], 'rationale': spec['rationale'],
              'limitations': spec.get('limitations', 'Only the declared outputs are compared; scientific validity is not established.')}
    write_new_tree(root, {report_path: encoded(report)})
    current['reproductions'].append({key: spec[key] for key in ('id', 'title', 'scope', 'required', 'inputs', 'by', 'rationale')})
    current['reproductions'][-1].update(status=status, run=run['id'], report=report_path, evidence=[report_path])
    atomic_json(root, '_pm/project-state.json', current)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--spec', required=True)
    args = parser.parse_args(argv)
    try:
        result = verify(args.project, load(local(args.project, args.spec, True)))
        print(encoded(result))
        return 0 if result['status'] == 'pass' else 1
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(encoded({'ok': False, 'error': str(error)}))
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
