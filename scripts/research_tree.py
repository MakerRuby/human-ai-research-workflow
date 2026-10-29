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

QID = re.compile(r'^Q-[0-9]{3,4}$')
HID = re.compile(r'^H-[0-9]{3,4}$')


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
        row = find(s.get('tasks', []), args.id, 'task')
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
    t.add_argument('action', choices=('link', 'intent'))
    t.add_argument('--id', required=True)
    t.add_argument('--serves', action='append')
    t.add_argument('--path')
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
