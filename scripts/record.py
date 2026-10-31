#!/usr/bin/env python3
"""Register decisions, artifacts and findings in project-state.json (stdlib only).

Like research_tree.py, every command edits a copy, runs the read-only checker and writes
only if no new error appears. Use it instead of ad hoc JSON edits. It records what was
decided or produced; it does not approve scientific results.
"""
import argparse
import re
import sys
from pathlib import Path

from project_io import digest, encoded, local, now, state
from research_tree import commit

CHECKPOINTS = {f'CP{i}' for i in range(10)}
DID = re.compile(r'^D-[0-9]{3,4}$')
FID = re.compile(r'^F-[0-9]{3,4}$')


def decision(root, args):
    if not DID.fullmatch(args.id):
        raise ValueError('Decision id must look like D-001')
    if args.checkpoint and args.checkpoint not in CHECKPOINTS:
        raise ValueError('checkpoint must be CP0-CP9')
    if args.skipped and not (args.checkpoint and args.rationale):
        raise ValueError('a skipped checkpoint needs --checkpoint and --rationale')
    if args.status == 'adopted' and not (args.by and args.authorization):
        raise ValueError('an adopted decision needs --by (real role) and --authorization (what was actually said)')
    current = state(root)

    def mutate(s):
        rows = s.setdefault('decisions', [])
        if any(r.get('id') == args.id for r in rows):
            raise ValueError(f'{args.id} already exists; supersede it with a new decision')
        row = {'id': args.id, 'title': args.title, 'status': args.status, 'record': args.record, 'findings': []}
        if args.checkpoint:
            row['checkpoint'] = args.checkpoint
        if args.skipped:
            row['checkpoint_outcome'] = 'skipped'
        if args.rationale:
            row['rationale'] = args.rationale
        if args.status == 'adopted':
            row.update(by=args.by, decided_at=now(), authorization=args.authorization,
                       evidence=args.evidence or [args.record])
        rows.append(row)
        return {'decision': args.id, 'status': args.status}
    return commit(root, current, mutate)


def artifact(root, args):
    file = local(root, args.path, must_exist=True)
    current = state(root)

    def mutate(s):
        rows = s.setdefault('artifacts', [])
        if any(r.get('id') == args.id for r in rows):
            raise ValueError(f'{args.id} already exists; register a new version id instead of overwriting')
        rows.append({'id': args.id, 'path': args.path, 'version': args.version, 'status': 'produced',
                     'depends_on': [{'id': d, 'version': v} for d, v in (x.split('@', 1) for x in args.depends_on or [])],
                     'required_checks': [], 'sha256': digest(file)})
        return {'artifact': args.id, 'sha256': rows[-1]['sha256']}
    return commit(root, current, mutate)


def finding(root, args):
    if not FID.fullmatch(args.id):
        raise ValueError('Finding id must look like F-001')
    current = state(root)

    # Findings cite the exact artifact version they were observed on (the checker requires it).
    versions = {a.get('id'): a.get('version') for a in current.get('artifacts', []) if isinstance(a, dict)}
    missing = [i for i in args.input or [] if i not in versions]
    if missing:
        raise ValueError('Register these artifacts before citing them: ' + ', '.join(missing))
    inputs = [{'id': i, 'version': versions[i]} for i in args.input or []]

    def mutate(s):
        rows = s.setdefault('findings', [])
        if any(r.get('id') == args.id for r in rows):
            raise ValueError(f'{args.id} already exists')
        rows.append({'id': args.id, 'title': args.title, 'status': 'observed', 'observed_at': now(), 'by': args.by,
                     'observation': args.observation, 'interpretation': args.interpretation,
                     'record': args.record, 'evidence': args.evidence, 'inputs': inputs, 'decisions': [], 'changes': []})
        return {'finding': args.id}
    return commit(root, current, mutate)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--project', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    d = sub.add_parser('decision')
    d.add_argument('--id', required=True)
    d.add_argument('--title', required=True)
    d.add_argument('--status', choices=('proposed', 'adopted'), default='proposed')
    d.add_argument('--record', default='_pm/DECISIONS.md')
    d.add_argument('--checkpoint', help='CP0-CP9 this decision answers')
    d.add_argument('--skipped', action='store_true', help='Checkpoint judged not applicable; requires --rationale')
    d.add_argument('--rationale')
    d.add_argument('--by')
    d.add_argument('--authorization')
    d.add_argument('--evidence', action='append')
    a = sub.add_parser('artifact')
    a.add_argument('--id', required=True)
    a.add_argument('--path', required=True)
    a.add_argument('--version', required=True)
    a.add_argument('--depends-on', action='append', help='ID@version')
    f = sub.add_parser('finding')
    f.add_argument('--input', action='append', required=True,
                   help='Artifact id the observation was made on (its registered version is used)')
    for key in ('id', 'title', 'by', 'observation', 'interpretation'):
        f.add_argument('--' + key, required=True)
    f.add_argument('--record', default='_pm/FINDINGS.md')
    f.add_argument('--evidence', action='append', required=True)
    args = parser.parse_args(argv)
    try:
        result = {'decision': decision, 'artifact': artifact, 'finding': finding}[args.command](
            Path(args.project).expanduser().resolve(), args)
        print(encoded({'ok': True, **result}))
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(encoded({'ok': False, 'error': str(error)}))
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
