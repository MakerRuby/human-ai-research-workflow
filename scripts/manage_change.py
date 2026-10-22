#!/usr/bin/env python3
"""Open an impact checklist and invalidate downstream records, or close fully treated changes."""
import argparse
from pathlib import Path
import sys

from check_project import Audit, check_project
from project_io import atomic_json, encoded, load, local, now, state


def open_change(root, spec):
    root = Path(root).resolve()
    current = state(root)
    if current.get('schema_version') != 2:
        raise ValueError('Schema 2 is required')
    for key in ('id', 'title', 'reason'):
        if not isinstance(spec.get(key), str) or not spec[key].strip():
            raise ValueError(f'Missing change {key}')
    if any(row['id'] == spec['id'] for row in current['changes']):
        raise ValueError('Change ID already exists')
    sources = spec.get('sources')
    artifacts = {row['id']: row for row in current['artifacts']}
    if not isinstance(sources, list) or not sources or any(s not in artifacts for s in sources):
        raise ValueError('Declare registered source artifact IDs')
    children = {key: [] for key in artifacts}
    for row in artifacts.values():
        for ref in row['depends_on']:
            if ref['id'] not in children:
                raise ValueError('Repair unknown artifact dependencies before opening change')
            children[ref['id']].append(row['id'])
    affected = Audit.descendants(set(sources), children)
    items = []

    def add(kind, row):
        item = {'kind': kind, 'id': row['id'], 'status': 'pending', 'rationale': '', 'evidence': []}
        if kind == 'artifact':
            item['version'] = row['version']
        items.append(item)

    for identity in sorted(affected):
        add('artifact', artifacts[identity])
        if identity not in sources:
            artifacts[identity]['status'] = 'stale'
    for row in current['tasks']:
        if set(row['outputs']) & affected or any(ref['id'] in affected for ref in row['inputs']):
            add('task', row)
            row['status'] = 'todo'
    check_index = {row['id']: row for row in current['checks']}
    affected_gates = {row['id'] for row in current['gates'] if set(row['artifacts']) & affected or any(check_index.get(c, {}).get('artifact') in affected for c in row['checks'])}
    gate_children = {row['id']: [] for row in current['gates']}
    for row in current['gates']:
        for parent in row['depends_on']:
            if parent not in gate_children:
                raise ValueError('Repair unknown gate dependencies first')
            gate_children[parent].append(row['id'])
    affected_gates = Audit.descendants(affected_gates, gate_children)
    for row in current['gates']:
        if row['id'] in affected_gates:
            add('gate', row)
            row['status'] = 'pending'
    for key, kind, field in (('reproductions', 'reproduction', 'inputs'), ('claims', 'claim', 'results'), ('review_items', 'review', 'inputs')):
        for row in current[key]:
            if any(ref['id'] in affected for ref in row[field]):
                add(kind, row)
                row['status'] = 'stale'
    change = {key: spec[key] for key in ('id', 'title', 'reason', 'sources')}
    change.update(status='open', opened_at=now(), findings=spec.get('findings', []),
                  decisions=spec.get('decisions', []), items=items)
    current['changes'].append(change)
    # In-memory audit prevents an incomplete/inconsistent mutation from being written.
    report = Audit(root, current).run()
    if not report['ok']:
        raise ValueError('Change preflight failed: ' + '; '.join(report['errors']))
    atomic_json(root, '_pm/project-state.json', current)
    return change


def close_change(root, identity, by, rationale):
    root = Path(root).resolve()
    current = state(root)
    row = next((r for r in current.get('changes', []) if r['id'] == identity), None)
    if row is None or row['status'] == 'closed':
        raise ValueError('Change is absent or already closed')
    if not by.strip() or not rationale.strip():
        raise ValueError('Actual responsible person/AI role and closure rationale are required')
    tables = {'artifact': 'artifacts', 'task': 'tasks', 'gate': 'gates', 'reproduction': 'reproductions',
              'claim': 'claims', 'review': 'review_items'}
    indexes = {kind: {r['id']: r for r in current[table]} for kind, table in tables.items()}
    for item in row['items']:
        if item.get('status') not in {'updated', 'unchanged'}:
            raise ValueError('Every impact item needs an explicit treatment')
        replacement = item.get('replacement', item['id'])
        if not isinstance(replacement, str) or replacement not in indexes[item['kind']]:
            raise ValueError('Replacement must identify a registered target of the same kind')
        if replacement != item['id'] and item['status'] != 'updated':
            raise ValueError('Replacement is an updated treatment, not unchanged')
        target = indexes[item['kind']][replacement]
        if item['kind'] == 'artifact' and (item.get('version') != target['version'] or target['status'] == 'stale'):
            raise ValueError('Artifact treatment must identify a current non-stale version')
        if item.get('status') == 'updated':
            allowed = {'task': {'done'}, 'gate': {'pass'}, 'reproduction': {'pass'},
                       'claim': {'supported', 'withdrawn'}, 'review': {'accepted', 'rejected', 'commented'}}
            if item['kind'] in allowed and target['status'] not in allowed[item['kind']]:
                raise ValueError('Updated target has unresolved status: ' + item['id'])
    row.update(status='closed', closed_at=now(), by=by, closure_rationale=rationale)
    report = Audit(root, current, verify_hashes=True).run()
    touched_repros = {item.get('replacement', item['id']) for item in row['items'] if item['kind'] == 'reproduction' and item['status'] == 'updated'}
    if touched_repros & set(report.get('governance', {}).get('invalid_or_pending_reproductions', [])):
        raise ValueError('Updated reproduction is not current')
    if not report['ok']:
        raise ValueError('Closure check failed: ' + '; '.join(report['errors']))
    atomic_json(root, '_pm/project-state.json', current)
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    commands = parser.add_subparsers(dest='action', required=True)
    opening = commands.add_parser('open')
    opening.add_argument('--spec', required=True)
    closing = commands.add_parser('close')
    closing.add_argument('--id', required=True)
    closing.add_argument('--by', required=True)
    closing.add_argument('--rationale', required=True)
    args = parser.parse_args(argv)
    try:
        result = open_change(args.project, load(local(args.project, args.spec, True))) if args.action == 'open' else close_change(args.project, args.id, args.by, args.rationale)
        print(encoded({'ok': True, 'change': result}))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(encoded({'ok': False, 'error': str(error)}))
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
