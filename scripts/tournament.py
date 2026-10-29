#!/usr/bin/env python3
"""Record and rank a hypothesis tournament (stdlib only).

The script never calls a model. Generation, review and pairwise judgement are done
by the host AI or by people; this tool validates append-only records, replays all
matches into an Elo-style internal preference ranking, and reports statistics.
Elo is a relative preference among judges, not scientific evidence.
"""
import argparse
import json
from pathlib import Path
import re
import sys

from project_io import atomic_json, encoded, load, local, now, state

TID = re.compile(r'^T[0-9]{2,4}$')
HID = re.compile(r'^T[0-9]{2,4}-H[0-9]{3,4}$')
STRATEGIES = {'literature', 'debate', 'decompose', 'analogy', 'contrarian', 'null', 'evolution', 'human', 'other'}
REVIEW_KINDS = {'initial', 'full', 'deep_verification', 'simulation', 'observation', 'human'}
VERDICTS = {'pass', 'revise', 'reject'}
H_STATUSES = {'active', 'eliminated', 'withdrawn'}
DEFAULT_CRITERIA = ['可检验性', '生物学合理性', '新颖性', '对结论的影响', '可行性']


def folder(root, tid):
    if not TID.fullmatch(tid or ''):
        raise ValueError('Tournament id must look like T01')
    return f'_pm/research/tournaments/{tid}'


def read_rows(root, relative):
    path = local(root, relative)
    if not path.is_file():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f'{relative}:{number}: expected a JSON object')
            rows.append(value)
    return rows


def append_row(root, relative, row):
    path = local(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8', newline='\n') as output:
        output.write(json.dumps(row, ensure_ascii=False) + '\n')


def config(root, tid):
    return load(local(root, folder(root, tid) + '/config.json', True))


def text(value):
    return isinstance(value, str) and bool(value.strip())


def hypotheses(root, tid):
    """Latest record per hypothesis id; status updates are appended, never rewritten."""
    latest = {}
    for row in read_rows(root, folder(root, tid) + '/hypotheses.jsonl'):
        if row.get('type') == 'status':
            if row.get('hypothesis') in latest:
                latest[row['hypothesis']] = dict(latest[row['hypothesis']], status=row['status'],
                                                 status_reason=row.get('reason'))
        else:
            latest[row['id']] = row
    return latest


def init(root, args):
    base = folder(root, args.id)
    if local(root, base + '/config.json').exists():
        raise ValueError(f'Tournament {args.id} already exists')
    current = state(root)
    questions = {q.get('id') for q in current.get('questions', []) if isinstance(q, dict)}
    if args.question not in questions:
        raise ValueError(f'Unknown question {args.question}; register it first with research_tree.py question add')
    criteria = args.criterion or DEFAULT_CRITERIA
    value = {'schema_version': 1, 'id': args.id, 'question': args.question, 'goal': args.goal,
             'criteria': [{'name': c, 'weight': 1} for c in criteria], 'constraints': [],
             'novelty_required': False, 'budget': {'hypotheses': args.max_hypotheses, 'matches': args.max_matches},
             'elo': {'initial': 1200, 'k': 32}, 'frozen': False, 'created_at': now(),
             'note': 'Elo 是评委相对偏好，不是证据。冻结前由负责人确认目标、标准与约束。'}
    atomic_json(root, base + '/config.json', value)
    for name in ('hypotheses.jsonl', 'reviews.jsonl', 'matches.jsonl'):
        path = local(root, f'{base}/{name}')
        if not path.exists():
            path.write_text('', encoding='utf-8')
    return {'created': base, 'config': value}


def freeze(root, args):
    base = folder(root, args.id)
    value = config(root, args.id)
    if value.get('frozen'):
        raise ValueError('Already frozen; change criteria through a recorded decision and a new tournament round')
    if not text(value.get('goal')) or not value.get('criteria'):
        raise ValueError('Goal and criteria are required before freezing')
    value.update(frozen=True, frozen_at=now(), frozen_by=args.by)
    atomic_json(root, base + '/config.json', value)
    return {'frozen': args.id, 'by': args.by}


def spec(path):
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError('Spec must be a JSON object')
    return value


def add(root, args):
    value, base = config(root, args.id), folder(root, args.id)
    if not value.get('frozen'):
        raise ValueError('Freeze the tournament configuration (checkpoint T1) before adding hypotheses')
    row = spec(args.spec)
    existing = hypotheses(root, args.id)
    if not row.get('id'):
        row['id'] = f'{args.id}-H{len(existing) + 1:03d}'
    if not HID.fullmatch(row['id']) or not row['id'].startswith(args.id + '-'):
        raise ValueError('Hypothesis id must look like T01-H001 and belong to this tournament')
    if row['id'] in existing:
        raise ValueError(f"Duplicate hypothesis {row['id']}; add an evolved version with parents instead")
    for key in ('statement', 'mechanism'):
        if not text(row.get(key)):
            raise ValueError(f'Hypothesis needs {key}')
    if not isinstance(row.get('predictions'), list) or not row['predictions'] or not all(text(p) for p in row['predictions']):
        raise ValueError('Hypothesis needs at least one discriminating prediction')
    if row.get('strategy') not in STRATEGIES:
        raise ValueError('strategy must be one of ' + ', '.join(sorted(STRATEGIES)))
    if row.get('origin') not in {'ai', 'human'}:
        raise ValueError('origin must be ai or human')
    parents = row.setdefault('parents', [])
    if not isinstance(parents, list) or any(p not in existing for p in parents):
        raise ValueError('parents must list existing hypothesis ids')
    if row['strategy'] == 'evolution' and not parents:
        raise ValueError('evolved hypotheses must name parents')
    budget = value.get('budget', {}).get('hypotheses')
    if isinstance(budget, int) and len(existing) >= budget:
        raise ValueError('Hypothesis budget reached; record a decision before extending it')
    row.update(status='active', added_at=now())
    row.setdefault('refs', [])
    append_row(root, base + '/hypotheses.jsonl', row)
    return {'added': row['id']}


def set_status(root, args):
    if args.status not in H_STATUSES:
        raise ValueError('status must be ' + ', '.join(sorted(H_STATUSES)))
    pool = hypotheses(root, args.id)
    if args.hypothesis not in pool:
        raise ValueError('Unknown hypothesis')
    if not text(args.reason):
        raise ValueError('A reason is required')
    if pool[args.hypothesis].get('strategy') == 'null' and args.status != 'active':
        adopted = {d.get('id') for d in state(root).get('decisions', []) if isinstance(d, dict) and d.get('status') == 'adopted'}
        if args.decision not in adopted:
            raise ValueError('The null baseline can only leave the pool through an adopted owner decision (--decision D-*)')
    append_row(root, folder(root, args.id) + '/hypotheses.jsonl',
               {'type': 'status', 'hypothesis': args.hypothesis, 'status': args.status,
                'reason': args.reason, 'decision': args.decision, 'at': now()})
    return {'hypothesis': args.hypothesis, 'status': args.status}


def review(root, args):
    base = folder(root, args.id)
    row = spec(args.spec)
    if row.get('hypothesis') not in hypotheses(root, args.id):
        raise ValueError('Review must target an existing hypothesis')
    if row.get('kind') not in REVIEW_KINDS:
        raise ValueError('kind must be one of ' + ', '.join(sorted(REVIEW_KINDS)))
    if row.get('verdict') not in VERDICTS:
        raise ValueError('verdict must be pass, revise or reject')
    if not text(row.get('reviewer')) or not text(row.get('rationale')):
        raise ValueError('Review needs reviewer and rationale')
    if row['kind'] == 'full' and not row.get('refs'):
        raise ValueError('Full review checks novelty and correctness against literature; cite refs (REF-* or locators)')
    criteria = {c['name'] for c in config(root, args.id).get('criteria', [])}
    for name, score in (row.get('scores') or {}).items():
        if name not in criteria or not isinstance(score, (int, float)) or not 1 <= score <= 5:
            raise ValueError(f'Score {name} must be a configured criterion scored 1-5')
    row['at'] = now()
    append_row(root, base + '/reviews.jsonl', row)
    return {'reviewed': row['hypothesis'], 'kind': row['kind'], 'verdict': row['verdict']}


def match(root, args):
    base = folder(root, args.id)
    row = spec(args.spec)
    pool = hypotheses(root, args.id)
    a, b = row.get('a'), row.get('b')
    if a not in pool or b not in pool or a == b:
        raise ValueError('a and b must be two different existing hypotheses')
    if row.get('winner') not in {'a', 'b', 'tie'}:
        raise ValueError('winner must be a, b or tie')
    if row.get('order') not in {'ab', 'ba'}:
        raise ValueError('order records which hypothesis the judge saw first: ab or ba')
    judge = row.get('judge')
    if not isinstance(judge, str) or not re.fullmatch(r'(ai|human):\S.*', judge):
        raise ValueError('judge must be ai:<context> or human:<name>')
    if not text(row.get('rationale')):
        raise ValueError('A match needs the judge rationale')
    budget = config(root, args.id).get('budget', {}).get('matches')
    if isinstance(budget, int) and len(read_rows(root, base + '/matches.jsonl')) >= budget:
        raise ValueError('Match budget reached; record a decision before extending it')
    row['at'] = now()
    append_row(root, base + '/matches.jsonl', row)
    return {'recorded': f'{a} vs {b}', 'winner': row['winner']}


def replay(pool, matches, initial, k, judges=None):
    ratings = {h: float(initial) for h in pool}
    games = {h: 0 for h in pool}
    for row in matches:
        if judges and not row['judge'].startswith(judges):
            continue
        a, b = row['a'], row['b']
        if a not in ratings or b not in ratings:
            continue
        expected = 1 / (1 + 10 ** ((ratings[b] - ratings[a]) / 400))
        score = {'a': 1.0, 'b': 0.0, 'tie': 0.5}[row['winner']]
        ratings[a] += k * (score - expected)
        ratings[b] -= k * (score - expected)
        games[a] += 1
        games[b] += 1
    return ratings, games


def kendall(first, second):
    shared = [h for h in first if h in second]
    concordant = discordant = 0
    for i, x in enumerate(shared):
        for y in shared[i + 1:]:
            product = (first.index(x) - first.index(y)) * (second.index(x) - second.index(y))
            concordant += product > 0
            discordant += product < 0
    total = concordant + discordant
    return None if total == 0 else round((concordant - discordant) / total, 3)


def rank(root, args):
    base, value = folder(root, args.id), config(root, args.id)
    pool = hypotheses(root, args.id)
    active = {h: r for h, r in pool.items() if r.get('status') == 'active'}
    matches = read_rows(root, base + '/matches.jsonl')
    reviews = read_rows(root, base + '/reviews.jsonl')
    elo = value.get('elo', {})
    initial, k = elo.get('initial', 1200), elo.get('k', 32)
    ratings, games = replay(pool, matches, initial, k)
    min_games = args.min_games
    order = sorted(active, key=lambda h: (-ratings[h], h))
    rejected = {r['hypothesis'] for r in reviews if r.get('verdict') == 'reject'}
    table = [{'id': h, 'elo': round(ratings[h], 1), 'matches': games[h], 'stable': games[h] >= min_games,
              'origin': pool[h].get('origin'), 'strategy': pool[h].get('strategy'),
              'review_reject': h in rejected, 'statement': pool[h].get('statement')} for h in order]
    strategies = {}
    for row in matches:
        for side in ('a', 'b'):
            h = row[side]
            name = pool.get(h, {}).get('strategy', 'unknown')
            if pool.get(h, {}).get('origin') == 'human':
                name = 'human'  # keep owner-proposed hypotheses out of AI strategy statistics
            entry = strategies.setdefault(name, {'matches': 0, 'wins': 0.0})
            entry['matches'] += 1
            entry['wins'] += 1.0 if row['winner'] == side else 0.5 if row['winner'] == 'tie' else 0.0
    for entry in strategies.values():
        entry['win_rate'] = round(entry['wins'] / entry['matches'], 3) if entry['matches'] else None
    # Plateau: top-k membership unchanged over the last window of matches.
    top_k, window = args.top_k, args.window
    plateau = False
    if len(matches) >= 2 * window:
        before, _ = replay(pool, matches[:-window], initial, k)
        prior = sorted(active, key=lambda h: (-before[h], h))[:top_k]
        plateau = set(prior) == set(order[:top_k])
    human = [m for m in matches if m['judge'].startswith('human:')]
    agreement = None
    if human:
        # Pairwise: share of human decisive judgements that the AI-only ranking reproduces.
        ai_ratings, _ = replay(pool, matches, initial, k, judges='ai:')
        decisive = [m for m in human if m['winner'] != 'tie']
        agree = sum(1 for m in decisive if (ai_ratings[m['a']] > ai_ratings[m['b']]) == (m['winner'] == 'a'))
        human_ratings, _ = replay(pool, matches, initial, k, judges='human:')
        judged = sorted({m[s] for m in human for s in ('a', 'b')} & set(active))
        agreement = {'pairwise_agreement': round(agree / len(decisive), 3) if decisive else None,
                     'decisive_human_matches': len(decisive),
                     'kendall_tau': kendall(sorted(judged, key=lambda h: (-human_ratings[h], h)),
                                            sorted(judged, key=lambda h: (-ai_ratings[h], h))),
                     'judged_hypotheses': len(judged),
                     'reliable': len(decisive) >= 5}
    # Next matches: prefer close ratings and few games; a played pair still needs its reverse order.
    seen_orders = {}
    for m in matches:
        key = (min(m['a'], m['b']), max(m['a'], m['b']))
        seen_orders.setdefault(key, set()).add(m['order'] if m['a'] == key[0] else {'ab': 'ba', 'ba': 'ab'}[m['order']])
    candidates = []
    for i, x in enumerate(order):
        for y in order[i + 1:]:
            key = (min(x, y), max(x, y))
            if len(seen_orders.get(key, ())) < 2:
                missing = sorted({'ab', 'ba'} - seen_orders.get(key, set()))[0]
                candidates.append((abs(ratings[x] - ratings[y]) + 20 * (games[x] + games[y]) + 100 * (key in seen_orders),
                                   key[0], key[1], missing))
    next_pairs = [{'a': a, 'b': b, 'order': o} for _, a, b, o in sorted(candidates)[:args.pairs]]
    nulls = [h for h in active if pool[h].get('strategy') == 'null']
    warnings = []
    if agreement and not agreement['reliable']:
        warnings.append('人评场数少于 5，人机一致率仅供参考')
    if agreement and agreement['pairwise_agreement'] is not None and agreement['pairwise_agreement'] < 0.6:
        warnings.append('人机一致率低于 0.6：先检查评价标准与评委偏差，再决定是否继续')
    if not nulls:
        warnings.append('池中没有 null（最无聊解释）基准假设')
    if any(not row['stable'] for row in table[:top_k]):
        warnings.append(f'前 {top_k} 名中有比较场数少于 {min_games} 的假设，排名不稳定')
    if not value.get('frozen'):
        warnings.append('配置未冻结，排名不可用于决策')
    result = {'tournament': args.id, 'generated_at': now(), 'ranking': table, 'strategies': strategies,
              'plateau': plateau, 'human_ai_agreement': agreement, 'next_pairs': next_pairs,
              'warnings': warnings, 'counts': {'hypotheses': len(pool), 'active': len(active),
                                               'reviews': len(reviews), 'matches': len(matches)},
              'scope': 'Elo 为评委相对偏好的内部排序，不是科学证据；用于选择优先检验的假设。'}
    atomic_json(root, base + '/ranking.json', result)
    lines = [f"# 锦标赛 {args.id} 排名报告", '', f"生成：{result['generated_at']}（可由 rank 重建）。{result['scope']}", '',
             '| 名次 | 假设 | Elo | 场数 | 稳定 | 来源 | 评审否决 | 表述 |', '|---|---|---|---|---|---|---|---|']
    for number, row in enumerate(table, 1):
        lines.append(f"| {number} | {row['id']} | {row['elo']} | {row['matches']} | {'是' if row['stable'] else '否'} | "
                     f"{row['origin']}/{row['strategy']} | {'是' if row['review_reject'] else ''} | "
                     f"{str(row['statement']).replace('|', '/')} |")
    lines += ['', f"平台期：{'是' if plateau else '否'}；人机一致：{agreement or '尚无人评'}", '',
              '提醒：' + ('；'.join(warnings) if warnings else '无'), '']
    with local(root, base + '/REPORT.md').open('w', encoding='utf-8', newline='\n') as output:
        output.write('\n'.join(lines))
    return result


def promote(root, args):
    pool = hypotheses(root, args.id)
    row = pool.get(args.hypothesis)
    if not row or row.get('status') != 'active':
        raise ValueError('Only an active tournament hypothesis can be promoted')
    if not re.fullmatch(r'H-[0-9]{3,4}', args.to):
        raise ValueError('Project hypothesis id must look like H-001')
    value = config(root, args.id)
    ranking_path = local(root, folder(root, args.id) + '/ranking.json')
    if not ranking_path.is_file():
        raise ValueError('Run rank first so the promotion records a ranking snapshot')
    current = state(root)
    current.setdefault('hypotheses', [])
    if any(h.get('id') == args.to for h in current['hypotheses']):
        raise ValueError(f'{args.to} already exists')
    if not local(root, '_pm/research/HYPOTHESES.md').is_file():
        raise ValueError('Create _pm/research/HYPOTHESES.md (template assets/research/HYPOTHESES.md) before promoting')
    adopted = {d.get('id') for d in current.get('decisions', []) if isinstance(d, dict) and d.get('status') == 'adopted'}
    if args.decision not in adopted:
        raise ValueError(f'Promotion needs the owner CP3 choice as an adopted decision; {args.decision} is not adopted')
    if value.get('question') not in {q.get('id') for q in current.get('questions', []) if isinstance(q, dict)}:
        raise ValueError('The tournament question is no longer registered')
    snapshot = load(ranking_path)
    place = next((n for n, r in enumerate(snapshot['ranking'], 1) if r['id'] == args.hypothesis), None)
    current['hypotheses'].append({
        'id': args.to, 'question': value.get('question'), 'statement': row['statement'],
        'origin': row.get('origin'), 'status': 'prioritized', 'predictions': row['predictions'],
        'source': {'tournament': args.id, 'hypothesis': args.hypothesis, 'rank': place,
                   'ranking': folder(root, args.id) + '/ranking.json', 'ranked_at': snapshot['generated_at']},
        'record': '_pm/research/HYPOTHESES.md', 'decision': args.decision, 'findings': []})
    atomic_json(root, '_pm/project-state.json', current)
    return {'promoted': args.hypothesis, 'as': args.to, 'rank': place}


def blind(root, args):
    """Judge packet for one pairing: content only, origin/strategy/parents hidden."""
    pool = hypotheses(root, args.id)
    if args.a not in pool or args.b not in pool or args.a == args.b:
        raise ValueError('a and b must be two different existing hypotheses')
    first, second = (args.a, args.b) if args.order == 'ab' else (args.b, args.a)
    keys = ('statement', 'mechanism', 'predictions', 'refs')
    criteria = [c['name'] for c in config(root, args.id).get('criteria', [])]
    return {'criteria': criteria, 'first': {k: pool[first].get(k) for k in keys},
            'second': {k: pool[second].get(k) for k in keys},
            'record_as': {'a': args.a, 'b': args.b, 'order': args.order,
                          'winner': 'a 或 b 或 tie（a/b 指 record_as 中的编号，不是展示顺序）'}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--project', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('init')
    p.add_argument('--id', required=True)
    p.add_argument('--question', required=True)
    p.add_argument('--goal', required=True)
    p.add_argument('--criterion', action='append')
    p.add_argument('--max-hypotheses', type=int, default=30)
    p.add_argument('--max-matches', type=int, default=200)
    p = sub.add_parser('freeze')
    p.add_argument('--id', required=True)
    p.add_argument('--by', required=True)
    for name in ('add', 'review', 'match'):
        p = sub.add_parser(name)
        p.add_argument('--id', required=True)
        p.add_argument('--spec', required=True)
    p = sub.add_parser('status')
    p.add_argument('--id', required=True)
    p.add_argument('--hypothesis', required=True)
    p.add_argument('--status', required=True)
    p.add_argument('--reason', required=True)
    p.add_argument('--decision', help='Adopted D-*; required to remove the null baseline')
    p = sub.add_parser('rank')
    p.add_argument('--id', required=True)
    p.add_argument('--top-k', type=int, default=3)
    p.add_argument('--window', type=int, default=10)
    p.add_argument('--min-games', type=int, default=4)
    p.add_argument('--pairs', type=int, default=5)
    p = sub.add_parser('promote')
    p.add_argument('--id', required=True)
    p.add_argument('--hypothesis', required=True)
    p.add_argument('--to', required=True)
    p.add_argument('--decision', required=True, help='Adopted D-* recording the owner choice at CP3')
    p = sub.add_parser('blind')
    p.add_argument('--id', required=True)
    p.add_argument('--a', required=True)
    p.add_argument('--b', required=True)
    p.add_argument('--order', choices=('ab', 'ba'), default='ab')
    args = parser.parse_args(argv)
    commands = {'init': init, 'freeze': freeze, 'add': add, 'review': review, 'match': match,
                'status': set_status, 'rank': rank, 'promote': promote, 'blind': blind}
    try:
        result = commands[args.command](Path(args.project).expanduser().resolve(), args)
        print(encoded({'ok': True, **result}))
        return 0
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(encoded({'ok': False, 'error': str(error)}))
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
