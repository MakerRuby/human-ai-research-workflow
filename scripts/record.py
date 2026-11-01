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
from research_tree import commit, find
from lifecycle import PROJECT_STATUSES, control, adopted, set_task

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


def check_record(root, args):
    current = state(root)
    proof = control(root, current, args.by, args.rationale, args.evidence)
    if args.status == 'waived' and (args.required or not args.waiver_reason):
        raise ValueError('Only a nonrequired check with --waiver-reason may be waived')

    def mutate(s):
        artifact = find(s.get('artifacts', []), args.artifact, 'artifact')
        if artifact['version'] != args.version:
            raise ValueError('Check version must match the current artifact')
        actual_hash = digest(local(root, artifact['path'], True))
        if artifact.get('sha256') != actual_hash:
            raise ValueError('Check target content differs from its registered hash')
        if any(r.get('id') == args.id for r in s['checks']):
            raise ValueError('Check id already exists; preserve its evidence and use a new id')
        s['checks'].append({'id': args.id, 'artifact': args.artifact, 'version': args.version,
                            'kind': args.kind, 'status': args.status, 'required': args.required,
                            'artifact_sha256': actual_hash,
                            **proof, **({'waiver_reason': args.waiver_reason} if args.waiver_reason else {})})
        return {'check': args.id, 'status': args.status}
    return commit(root, current, mutate)


def accept(root, args):
    current = state(root)
    proof = control(root, current, args.by, args.rationale, args.evidence)

    def mutate(s):
        row = find(s['artifacts'], args.id, 'artifact')
        if row.get('status') == 'stale' or row.get('lifecycle') == 'retired':
            raise ValueError('Cannot accept stale or retired work')
        if row.get('sha256') != digest(local(root, row['path'], True)):
            raise ValueError('Artifact content differs from its registered hash')
        needed = list(dict.fromkeys(row.get('required_checks', []) + (args.check or []) +
                      [c['id'] for c in s['checks'] if c.get('artifact') == args.id
                       and c.get('version') == row['version'] and c.get('required')]))
        if not needed:
            raise ValueError('Acceptance needs at least one necessary completed check')
        for identity in needed:
            check = find(s['checks'], identity, 'check')
            if (check.get('artifact') != args.id or check.get('version') != row['version']
                    or check.get('status') != 'pass'):
                raise ValueError('All necessary checks must be current passes for this artifact')
            if check.get('artifact_sha256', row['sha256']) != row['sha256']:
                raise ValueError('Check content hash does not match the registered artifact')
            check['required'] = True
        if 'acceptance' in row:
            row.setdefault('acceptance_history', []).append(row['acceptance'])
        row.update(status='accepted', required_checks=needed, acceptance=proof)
        return {'artifact': args.id, 'status': row['status'], 'checks': needed}
    return commit(root, current, mutate)


def decision_set(root, args):
    current = state(root)
    proof = control(root, current, args.by, args.rationale, args.evidence)

    def mutate(s):
        row = find(s['decisions'], args.id, 'decision')
        if row.get('status') not in {'proposed', 'adopted'}:
            raise ValueError('This decision is already withdrawn/superseded; preserve the closed record')
        if args.status == 'superseded':
            if row['status'] != 'adopted':
                raise ValueError('An unadopted proposal may be withdrawn; do not invent prior adoption')
            if args.superseded_by == args.id:
                raise ValueError('A decision cannot supersede itself')
            adopted(s, args.superseded_by)
        row.setdefault('status_history', []).append({'status': row['status'], 'transition': proof})
        row.update(status=args.status, disposition=proof)
        if args.status == 'superseded':
            row['superseded_by'] = args.superseded_by
        return {'decision': args.id, 'status': row['status']}
    return commit(root, current, mutate)


def project_execution(root, args):
    current = state(root)
    proof = control(root, current, args.by, args.rationale, args.evidence, args.decision)
    adopted(current, args.decision)
    if args.objective_achieved == 'yes' and not args.objective_evidence:
        raise ValueError('An achieved objective needs explicit --objective-evidence; stopping is not success')
    for path in args.objective_evidence or []:
        local(root, path, must_exist=True)

    def mutate(s):
        project = s['project']
        previous = project.get('execution')
        if previous:
            if (previous['status'] != 'active' and args.status == 'active'
                    and previous.get('decision') == args.decision):
                raise ValueError('Resumption needs a new adopted decision, not the stopping decision')
            project.setdefault('execution_history', []).append(previous)
        project['execution'] = dict(proof, status=args.status)
        if args.objective_achieved is not None:
            if 'objective_assessment' in project:
                project.setdefault('objective_history', []).append(
                    {'achieved': project.get('objective_achieved'), 'assessment': project['objective_assessment']})
            project['objective_achieved'] = {'yes': True, 'no': False, 'unknown': None}[args.objective_achieved]
            project['objective_assessment'] = dict(proof, evidence=args.objective_evidence or args.evidence)
        frozen = []
        if args.status != 'active':
            for row in s['tasks']:
                if row['status'] in {'todo', 'doing', 'blocked'} or (
                        args.status == 'stopped' and row['status'] == 'paused'):
                    set_task(row, args.status, proof)
                    frozen.append(row['id'])
        return {'execution': args.status, 'objective_achieved': project.get('objective_achieved'),
                'tasks_changed': frozen, 'tasks_resumed': []}
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
    def proof_args(p):
        p.add_argument('--by', required=True, help='Actual role; the tool does not grant approval')
        p.add_argument('--rationale', required=True)
        p.add_argument('--evidence', action='append', required=True, help='Existing project-relative evidence file')
    c = sub.add_parser('check', help='Record an actual completed check, without executing it')
    for key in ('id', 'artifact', 'version'):
        c.add_argument('--' + key, required=True)
    c.add_argument('--kind', choices=('machine', 'professional', 'source'), required=True)
    c.add_argument('--status', choices=('pass', 'fail', 'waived'), required=True)
    c.add_argument('--required', action='store_true')
    c.add_argument('--waiver-reason')
    proof_args(c)
    a = sub.add_parser('accept', help='Atomically link completed checks and record scoped acceptance')
    a.add_argument('--id', required=True)
    a.add_argument('--check', action='append')
    proof_args(a)
    d = sub.add_parser('decision-set', help='Withdraw a proposal or supersede an adopted decision; keep its history')
    d.add_argument('--id', required=True)
    d.add_argument('--status', choices=('withdrawn', 'superseded'), required=True)
    d.add_argument('--superseded-by')
    proof_args(d)
    p = sub.add_parser('project', help='Record execution control separately from objective achievement')
    p.add_argument('--status', choices=sorted(PROJECT_STATUSES), required=True)
    p.add_argument('--decision', required=True)
    p.add_argument('--objective-achieved', choices=('yes', 'no', 'unknown'))
    p.add_argument('--objective-evidence', action='append')
    proof_args(p)
    args = parser.parse_args(argv)
    try:
        result = {'decision': decision, 'artifact': artifact, 'finding': finding,
                  'check': check_record, 'accept': accept, 'decision-set': decision_set,
                  'project': project_execution}[args.command](
            Path(args.project).expanduser().resolve(), args)
        print(encoded({'ok': True, **result}))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(encoded({'ok': False, 'error': str(error)}))
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
