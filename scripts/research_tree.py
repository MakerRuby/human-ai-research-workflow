#!/usr/bin/env python3
"""Maintain the question tree, project hypotheses and task purpose links (stdlib only).

Every command applies its change to a copy of project-state.json, runs the read-only
checker on the copy, and writes only if the change introduces no new errors. It
records what people and the AI decided; it does not judge scientific value.
"""
import argparse
import copy
import re
import sys
from pathlib import Path

from check_project import Audit
from project_io import atomic_json, digest, encoded, local, now, state
from lifecycle import TASK_STATUSES, CONTROLLED_TASK_STATUSES, control, adopted, require_active, set_task

QID = re.compile(r'^Q-[0-9]{3,4}$')
HID = re.compile(r'^H-[0-9]{3,4}$')
TID = re.compile(r'^T-[0-9]{3,4}$')


def commit(root, current, mutate):
    before = set(Audit(root, current).run()['errors'])
    proposed = copy.deepcopy(current)
    result = mutate(proposed)
    after = Audit(root, proposed).run()
    introduced = [e for e in after['errors'] if e not in before]
    if introduced:
        raise ValueError('Change refused; it would introduce errors: ' + '; '.join(introduced))
    atomic_json(root, '_pm/project-state.json', proposed)
    return dict(result, warnings=after['warnings'])


def find(rows, identity, label):
    row = next((r for r in rows if isinstance(r, dict) and r.get('id') == identity), None)
    if row is None:
        raise ValueError(f'Unknown {label} {identity}')
    return row


def extend(row, key, values):
    if values:
        row.setdefault(key, [])
        row[key].extend(v for v in values if v not in row[key])


def question(root, args):
    current = state(root)

    def mutate(s):
        rows = s.setdefault('questions', [])
        if args.action == 'add':
            if not QID.fullmatch(args.id):
                raise ValueError('Question id must look like Q-001')
            if any(r.get('id') == args.id for r in rows):
                raise ValueError(f'{args.id} already exists')
            if args.statement is None or args.clarity is None:
                raise ValueError('add needs --statement and --clarity')
            row = {'id': args.id, 'statement': args.statement, 'clarity': args.clarity,
                   'status': args.status or 'open', 'findings': [], 'claims': [], 'decisions': []}
            rows.append(row)
        else:
            row = find(rows, args.id, 'question')
        for key in ('statement', 'clarity', 'status', 'parent', 'type'):
            value = getattr(args, key)
            if value is not None and not (args.action == 'add' and key in ('statement', 'clarity', 'status')):
                row[key] = value
        extend(row, 'findings', args.add_finding)
        extend(row, 'claims', args.add_claim)
        extend(row, 'decisions', args.add_decision)
        row['updated_at'] = now()
        return {'question': args.id, 'action': args.action}
    return commit(root, current, mutate)


def hypothesis(root, args):
    current = state(root)

    def mutate(s):
        rows = s.setdefault('hypotheses', [])
        if args.action == 'add':
            if not HID.fullmatch(args.id):
                raise ValueError('Hypothesis id must look like H-001')
            if any(r.get('id') == args.id for r in rows):
                raise ValueError(f'{args.id} already exists')
            if not (args.question and args.statement and args.prediction and args.origin):
                raise ValueError('add needs --question, --statement, --prediction and --origin')
            rows.append({'id': args.id, 'question': args.question, 'statement': args.statement,
                         'predictions': list(args.prediction), 'origin': args.origin,
                         'status': args.status or 'candidate', 'record': '_pm/research/HYPOTHESES.md',
                         'findings': []})
            row = rows[-1]
        else:
            row = find(rows, args.id, 'hypothesis')
            if args.status:
                row['status'] = args.status
            if args.statement:
                row['statement'] = args.statement
            extend(row, 'predictions', args.prediction)
        extend(row, 'findings', args.add_finding)
        extend(row, 'derived_from', args.derived_from)
        extend(row, 'validated_on', args.validated_on)
        if args.independence:
            row['independence'] = args.independence
        row['updated_at'] = now()
        return {'hypothesis': args.id, 'action': args.action}
    return commit(root, current, mutate)


def task(root, args):
    current = state(root)

    def mutate(s):
        rows = s.setdefault('tasks', [])
        if args.action == 'add':
            if not TID.fullmatch(args.id):
                raise ValueError('Task id must look like T-001')
            if any(r.get('id') == args.id for r in rows):
                raise ValueError(f'{args.id} already exists')
            if not args.title or not args.title.strip():
                raise ValueError('add needs a nonempty --title')
            inputs = []
            for value in args.input or []:
                identity, separator, version = value.partition('@')
                if not separator or not identity or not version:
                    raise ValueError('Task inputs must use ID@version')
                artifact = find(s.get('artifacts', []), identity, 'artifact')
                if (artifact.get('version') != version or artifact.get('status') == 'stale'
                        or artifact.get('lifecycle') == 'retired'):
                    raise ValueError('Task input version is stale or retired')
                inputs.append({'id': identity, 'version': version})
            row = {'id': args.id, 'title': args.title, 'status': 'todo', 'inputs': inputs, 'outputs': []}
            extend(row, 'serves', args.serves)
            rows.append(row)
            return {'task': args.id, 'action': 'add'}
        row = find(rows, args.id, 'task')
        if args.action == 'set':
            if args.status is None and not args.output:
                raise ValueError('set needs --status or --output')
            record = control(root, s, args.by, args.rationale, args.evidence, args.decision)
            target = args.status or row['status']
            if target in CONTROLLED_TASK_STATUSES or row['status'] in CONTROLLED_TASK_STATUSES:
                adopted(s, args.decision)
                previous = row.get('status_record', {}).get('decision')
                if target not in CONTROLLED_TASK_STATUSES and args.decision == previous:
                    raise ValueError('Resumption needs a new adopted decision, not the stopping decision')
            if target in {'doing', 'todo'}:
                require_active(s)
            for identity in args.output or []:
                find(s.get('artifacts', []), identity, 'artifact')
            extend(row, 'outputs', args.output)
            if args.output and args.status is None:
                row.setdefault('output_history', []).append({'outputs': list(args.output), 'record': record})
            if args.status is not None:
                set_task(row, target, record)
            return {'task': args.id, 'status': row['status'], 'outputs': row['outputs']}
        if args.action == 'link':
            if not args.serves:
                raise ValueError('link needs at least one --serves')
            extend(row, 'serves', args.serves)
            return {'task': args.id, 'serves': row['serves']}
        if not args.path:
            raise ValueError('intent needs --path to the written intent brief')
        file = local(root, args.path, must_exist=True)
        if isinstance(row.get('intent'), dict):
            row.setdefault('intent_history', []).append(row['intent'])
        row['intent'] = {'path': args.path, 'written_at': now(), 'sha256': digest(file)}
        return {'task': args.id, 'intent': row['intent']}
    return commit(root, current, mutate)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--project', required=True)
    sub = parser.add_subparsers(dest='entity', required=True)
    q = sub.add_parser('question')
    q.add_argument('action', choices=('add', 'set'))
    q.add_argument('--id', required=True)
    q.add_argument('--statement')
    q.add_argument('--clarity', type=int)
    q.add_argument('--status')
    q.add_argument('--parent')
    q.add_argument('--type')
    q.add_argument('--add-finding', action='append')
    q.add_argument('--add-claim', action='append')
    q.add_argument('--add-decision', action='append')
    h = sub.add_parser('hypothesis')
    h.add_argument('action', choices=('add', 'set'))
    h.add_argument('--id', required=True)
    h.add_argument('--question')
    h.add_argument('--statement')
    h.add_argument('--prediction', action='append')
    h.add_argument('--origin', choices=('ai', 'human'))
    h.add_argument('--status')
    h.add_argument('--add-finding', action='append')
    h.add_argument('--derived-from', action='append', help='Artifact the hypothesis was generated from')
    h.add_argument('--validated-on', action='append', help='Independent artifact used to test it')
    h.add_argument('--independence', help='Why shared upstream inputs do not compromise independence')
    t = sub.add_parser('task')
    t.add_argument('action', choices=('add', 'link', 'intent', 'set'))
    t.add_argument('--id', required=True)
    t.add_argument('--serves', action='append')
    t.add_argument('--title', help='Required for add; new tasks start as todo')
    t.add_argument('--input', action='append', help='Versioned artifact input for add: ID@version')
    t.add_argument('--path')
    t.add_argument('--status', choices=sorted(TASK_STATUSES))
    t.add_argument('--output', action='append', help='Existing artifact id; done still requires accepted current outputs')
    t.add_argument('--by')
    t.add_argument('--rationale')
    t.add_argument('--evidence', action='append')
    t.add_argument('--decision', help='Actual adopted control/resumption decision, not inferred permission')
    args = parser.parse_args(argv)
    handlers = {'question': question, 'hypothesis': hypothesis, 'task': task}
    try:
        result = handlers[args.entity](Path(args.project).expanduser().resolve(), args)
        print(encoded({'ok': True, **result}))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(encoded({'ok': False, 'error': str(error)}))
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
