#!/usr/bin/env python3
"""v4 behaviour tests: study designs, question tree, tournament and capability registry."""
from argparse import Namespace
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import check_project
import init_project
import registry_search
import research_tree
import tournament


class V4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hairw-v4-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'

    def init(self, **overrides):
        values = dict(target=str(self.root), name='v4 测试', scale='L', profile='research',
                      dry_run=False, date='2026-10-29', design=None)
        values.update(overrides)
        return init_project.initialize(Namespace(**values))

    def state(self):
        return json.loads((self.root / '_pm/project-state.json').read_text(encoding='utf-8'))

    def save(self, state):
        (self.root / '_pm/project-state.json').write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')

    def audit(self):
        return check_project.check_project(self.root)

    def spec(self, name, value):
        path = Path(self.temp.name) / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return str(path)

    def cli(self, *argv):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = tournament.main(['--project', str(self.root), *argv])
        return code, json.loads(buffer.getvalue())

    # Initialization
    def test_research_init_creates_thinking_and_narrative_layers(self):
        created = self.init()['created']
        for path in ('_pm/research/HYPOTHESES.md', 'references/SEARCH_LOG.md', 'references/EVIDENCE_MAP.md',
                     'manuscript/NARRATIVE.md'):
            self.assertIn(path, created)
        self.assertNotIn('_pm/research/EXPERIMENTS.md', created)
        current = self.state()
        self.assertEqual(current['questions'], [])
        self.assertEqual([g['id'] for g in current['gates']], ['G1', 'G2', 'G3'])
        self.assertTrue(self.audit()['ok'])

    def test_designs_add_experiment_register_and_extra_gates(self):
        created = self.init(design=['secondary', 'animal', 'clinical_trial'])['created']
        self.assertIn('_pm/research/EXPERIMENTS.md', created)
        gates = {g['id']: g['depends_on'] for g in self.state()['gates']}
        self.assertEqual(gates['E1'], ['G1'])
        self.assertEqual(gates['R1'], ['G3'])
        self.assertEqual(self.state()['project']['designs'], ['secondary', 'animal', 'clinical_trial'])
        self.assertTrue(self.audit()['ok'])

    def test_design_requires_research_profile(self):
        with self.assertRaises(ValueError):
            self.init(profile='general', design=['wet_lab'])

    def test_general_project_has_no_research_collections(self):
        self.init(profile='general', scale='M')
        self.assertNotIn('questions', self.state())
        self.assertTrue(self.audit()['ok'])

    # Question tree and purpose links
    def test_question_tree_hypothesis_and_task_links(self):
        self.init()
        current = self.state()
        current['questions'] = [
            {'id': 'Q-001', 'statement': '根问题', 'clarity': 2, 'status': 'open'},
            {'id': 'Q-002', 'statement': '子问题', 'clarity': 3, 'status': 'open', 'parent': 'Q-001', 'type': 'wet_lab'}]
        current['hypotheses'] = [{'id': 'H-001', 'question': 'Q-002', 'statement': 'X 介导 Y', 'status': 'prioritized',
                                  'origin': 'human', 'predictions': ['敲低 X 后 Y 下降'], 'findings': []}]
        self.save(current)
        report = self.audit()
        self.assertTrue(report['ok'], report['errors'])
        self.assertEqual(report['governance']['research_model']['hypotheses_in_test'], ['H-001'])

    def test_research_model_rejects_broken_links(self):
        self.init()
        current = self.state()
        current['questions'] = [
            {'id': 'Q-001', 'statement': '甲', 'clarity': 7, 'status': 'open', 'parent': 'Q-002'},
            {'id': 'Q-002', 'statement': '乙', 'clarity': 2, 'status': 'answered', 'parent': 'Q-001'}]
        current['hypotheses'] = [{'id': 'H-001', 'question': 'Q-404', 'statement': 's', 'status': 'supported',
                                  'origin': 'model', 'predictions': []}]
        self.save(current)
        errors = ' '.join(self.audit()['errors'])
        for text in ('clarity must be', 'cycle', 'answered question needs', 'registered question',
                     'discriminating prediction', 'origin must be', 'tested hypothesis needs findings'):
            self.assertIn(text, errors)

    def test_unlinked_research_task_warns_and_unknown_serves_fails(self):
        self.init()
        current = self.state()
        current['questions'] = [{'id': 'Q-001', 'statement': '根', 'clarity': 2, 'status': 'open'}]
        current['tasks'] = [{'id': 'T-A', 'status': 'todo', 'inputs': [], 'outputs': []},
                            {'id': 'T-B', 'status': 'todo', 'inputs': [], 'outputs': [], 'serves': ['Q-001']}]
        self.save(current)
        report = self.audit()
        self.assertTrue(report['ok'], report['errors'])
        self.assertTrue(any('T-A' in w and 'serves' in w for w in report['warnings']))
        current['tasks'][1]['serves'] = ['H-999']
        self.save(current)
        self.assertIn('unknown question/hypothesis/claim', ' '.join(self.audit()['errors']))

    def test_supported_synthesis_claim_needs_named_reviewer(self):
        self.init()
        (self.root / 'results').mkdir()
        (self.root / 'results/r.csv').write_text('x\n', encoding='utf-8')
        (self.root / 'manuscript/sections').mkdir(parents=True)
        (self.root / 'manuscript/sections/results.md').write_text('text\n', encoding='utf-8')
        current = self.state()
        current['artifacts'] = [{'id': 'RES', 'path': 'results/r.csv', 'version': 'v1', 'status': 'produced',
                                 'depends_on': [], 'required_checks': []}]
        current['claims'] = [{'id': 'CLAIM-1', 'statement': '综合解释', 'strength': 'moderate', 'status': 'supported',
                              'basis': 'synthesis', 'results': [{'id': 'RES', 'version': 'v1'}],
                              'locations': ['manuscript/sections/results.md'], 'findings': [],
                              'evidence': ['results/r.csv']}]
        self.save(current)
        self.assertIn('named human reviewer', ' '.join(self.audit()['errors']))
        current['claims'][0]['reviewed_by'] = '负责人'
        self.save(current)
        self.assertTrue(self.audit()['ok'], self.audit()['errors'])

    def test_invalid_designs_fail(self):
        self.init()
        current = self.state()
        current['project']['designs'] = ['astrology']
        self.save(current)
        self.assertIn('project.designs', ' '.join(self.audit()['errors']))

    # Tournament
    def prepare_tournament(self):
        self.init()
        current = self.state()
        current['questions'] = [{'id': 'Q-001', 'statement': '根', 'clarity': 2, 'status': 'open'}]
        self.save(current)
        self.assertEqual(self.cli('init', '--id', 'T01', '--question', 'Q-001', '--goal', '解释机制')[0], 0)

    def hypothesis(self, n, strategy='literature', origin='ai'):
        return self.spec(f'h{n}.json', {'statement': f'假设{n}', 'mechanism': f'机制{n}', 'predictions': [f'预测{n}'],
                                        'strategy': strategy, 'origin': origin})

    def test_tournament_requires_freeze_and_valid_records(self):
        self.prepare_tournament()
        code, out = self.cli('add', '--id', 'T01', '--spec', self.hypothesis(1))
        self.assertEqual(code, 1)
        self.assertIn('Freeze', out['error'])
        self.assertEqual(self.cli('freeze', '--id', 'T01', '--by', '负责人')[0], 0)
        self.assertEqual(self.cli('freeze', '--id', 'T01', '--by', '负责人')[0], 1)
        bad = self.spec('bad.json', {'statement': 's', 'mechanism': 'm', 'predictions': [], 'strategy': 'literature', 'origin': 'ai'})
        self.assertEqual(self.cli('add', '--id', 'T01', '--spec', bad)[0], 1)
        evolved = self.spec('evo.json', {'statement': 's', 'mechanism': 'm', 'predictions': ['p'], 'strategy': 'evolution', 'origin': 'ai'})
        self.assertIn('parents', self.cli('add', '--id', 'T01', '--spec', evolved)[1]['error'])
        self.assertEqual(self.cli('add', '--id', 'T01', '--spec', self.hypothesis(1))[0], 0)
        self.assertEqual(self.cli('add', '--id', 'T01', '--spec', self.hypothesis(2, 'null'))[0], 0)
        no_refs = self.spec('r.json', {'hypothesis': 'T01-H001', 'kind': 'full', 'verdict': 'pass', 'reviewer': 'ai:r', 'rationale': 'ok'})
        self.assertIn('refs', self.cli('review', '--id', 'T01', '--spec', no_refs)[1]['error'])
        bad_judge = self.spec('m.json', {'a': 'T01-H001', 'b': 'T01-H002', 'winner': 'a', 'order': 'ab', 'judge': 'gpt', 'rationale': 'r'})
        self.assertIn('judge', self.cli('match', '--id', 'T01', '--spec', bad_judge)[1]['error'])

    def test_rank_replays_matches_and_promote_registers_hypothesis(self):
        self.prepare_tournament()
        self.cli('freeze', '--id', 'T01', '--by', '负责人')
        for n, strategy, origin in ((1, 'literature', 'ai'), (2, 'null', 'ai'), (3, 'literature', 'human')):
            self.cli('add', '--id', 'T01', '--spec', self.hypothesis(n, strategy, origin))
        for number, (a, b, winner, order) in enumerate((('T01-H001', 'T01-H002', 'a', 'ab'), ('T01-H001', 'T01-H002', 'a', 'ba'),
                                                         ('T01-H001', 'T01-H003', 'a', 'ab'), ('T01-H002', 'T01-H003', 'tie', 'ab'))):
            self.assertEqual(self.cli('match', '--id', 'T01', '--spec', self.spec(f'm{number}.json', {
                'a': a, 'b': b, 'winner': winner, 'order': order, 'judge': 'ai:critic', 'rationale': 'r'}))[0], 0)
        self.cli('match', '--id', 'T01', '--spec', self.spec('mh.json', {
            'a': 'T01-H003', 'b': 'T01-H001', 'winner': 'b', 'order': 'ab', 'judge': 'human:负责人', 'rationale': 'r'}))
        code, ranking = self.cli('rank', '--id', 'T01', '--min-games', '2')
        self.assertEqual(code, 0)
        self.assertEqual(ranking['ranking'][0]['id'], 'T01-H001')
        self.assertIn('human', ranking['strategies'])
        self.assertEqual(ranking['human_ai_agreement']['pairwise_agreement'], 1.0)
        self.assertFalse(ranking['human_ai_agreement']['reliable'])
        self.assertTrue(all(p['a'] != p['b'] for p in ranking['next_pairs']))
        self.assertTrue((self.root / '_pm/research/tournaments/T01/REPORT.md').is_file())
        # Rebuilding from the append-only log gives the same ranking.
        self.assertEqual(self.cli('rank', '--id', 'T01', '--min-games', '2')[1]['ranking'], ranking['ranking'])
        code, out = self.cli('promote', '--id', 'T01', '--hypothesis', 'T01-H001', '--to', 'H-001', '--decision', 'D-404')
        self.assertIn('adopted decision', out['error'])
        self.adopt_decision('D-001')
        code, out = self.cli('promote', '--id', 'T01', '--hypothesis', 'T01-H001', '--to', 'H-001', '--decision', 'D-001')
        self.assertEqual(code, 0, out)
        hypothesis = self.state()['hypotheses'][0]
        self.assertEqual((hypothesis['question'], hypothesis['source']['rank'], hypothesis['decision']), ('Q-001', 1, 'D-001'))
        self.assertTrue(self.audit()['ok'], self.audit()['errors'])
        self.assertEqual(self.cli('promote', '--id', 'T01', '--hypothesis', 'T01-H002', '--to', 'H-001', '--decision', 'D-001')[0], 1)

    def adopt_decision(self, identity):
        evidence = self.root / '_pm/reviews/cp3.md'
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text('SYNTHETIC TEST ONLY: owner choice at CP3\n', encoding='utf-8')
        current = self.state()
        current['decisions'].append({'id': identity, 'title': 'CP3 选择', 'status': 'adopted', 'record': '_pm/DECISIONS.md',
                                     'findings': [], 'by': '负责人', 'decided_at': '2026-10-29T10:00:00+08:00',
                                     'authorization': '会话中确认', 'evidence': ['_pm/reviews/cp3.md']})
        self.save(current)

    def test_null_baseline_needs_owner_decision_to_leave(self):
        self.prepare_tournament()
        self.cli('freeze', '--id', 'T01', '--by', '负责人')
        self.cli('add', '--id', 'T01', '--spec', self.hypothesis(1, 'null'))
        args = ('status', '--id', 'T01', '--hypothesis', 'T01-H001', '--status', 'eliminated', '--reason', '已排除')
        self.assertIn('null baseline', self.cli(*args)[1]['error'])
        self.adopt_decision('D-002')
        self.assertEqual(self.cli(*args, '--decision', 'D-002')[0], 0)

    def test_blind_packet_hides_origin_and_respects_order(self):
        self.prepare_tournament()
        self.cli('freeze', '--id', 'T01', '--by', '负责人')
        self.cli('add', '--id', 'T01', '--spec', self.hypothesis(1, 'null', 'ai'))
        self.cli('add', '--id', 'T01', '--spec', self.hypothesis(2, 'literature', 'human'))
        code, packet = self.cli('blind', '--id', 'T01', '--a', 'T01-H001', '--b', 'T01-H002', '--order', 'ba')
        self.assertEqual(code, 0)
        self.assertEqual(packet['first']['statement'], '假设2')
        text = json.dumps(packet['first'], ensure_ascii=False) + json.dumps(packet['second'], ensure_ascii=False)
        for hidden in ('origin', 'strategy', 'parents', 'human', 'null'):
            self.assertNotIn(hidden, text)
        self.assertEqual(packet['record_as']['order'], 'ba')

    def test_unknown_question_and_budget_are_enforced(self):
        self.init()
        current = self.state()
        current['questions'] = [{'id': 'Q-001', 'statement': '根', 'clarity': 2, 'status': 'open'}]
        self.save(current)
        self.assertIn('Unknown question', self.cli('init', '--id', 'T02', '--question', 'Q-404', '--goal', 'g')[1]['error'])
        self.cli('init', '--id', 'T02', '--question', 'Q-001', '--goal', 'g', '--max-hypotheses', '1')
        self.cli('freeze', '--id', 'T02', '--by', '负责人')
        self.assertEqual(self.cli('add', '--id', 'T02', '--spec', self.hypothesis(1))[0], 0)
        self.assertIn('budget', self.cli('add', '--id', 'T02', '--spec', self.hypothesis(2))[1]['error'])

    # Question-tree helper, independence and intent timing
    def tree(self, *argv):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = research_tree.main(['--project', str(self.root), *argv])
        return code, json.loads(buffer.getvalue())

    def artifact(self, identity, parents=()):
        path = self.root / f'data/{identity}.csv'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(identity + '\n', encoding='utf-8')
        current = self.state()
        current['artifacts'].append({'id': identity, 'path': f'data/{identity}.csv', 'version': 'v1', 'status': 'produced',
                                     'depends_on': [{'id': p, 'version': 'v1'} for p in parents], 'required_checks': []})
        self.save(current)

    def test_research_tree_writes_only_valid_changes(self):
        self.init()
        self.assertEqual(self.tree('question', 'add', '--id', 'Q-001', '--statement', '根', '--clarity', '1')[0], 0)
        code, out = self.tree('question', 'add', '--id', 'Q-002', '--statement', '子', '--clarity', '2', '--parent', 'Q-404')
        self.assertEqual(code, 1)
        self.assertIn('unknown parent', out['error'])
        self.assertEqual([q['id'] for q in self.state()['questions']], ['Q-001'])  # refused change left no trace
        self.assertEqual(self.tree('question', 'add', '--id', 'Q-002', '--statement', '子', '--clarity', '2', '--parent', 'Q-001')[0], 0)
        self.assertIn('cycle', self.tree('question', 'set', '--id', 'Q-001', '--parent', 'Q-002')[1]['error'])
        self.assertEqual(self.tree('question', 'set', '--id', 'Q-001', '--clarity', '3')[0], 0)
        self.assertEqual(self.tree('hypothesis', 'add', '--id', 'H-001', '--question', 'Q-002', '--statement', 'X 介导 Y',
                                   '--prediction', '敲低 X 后 Y 下降', '--origin', 'human')[0], 0)
        self.assertIn('needs findings', self.tree('hypothesis', 'set', '--id', 'H-001', '--status', 'supported')[1]['error'])
        self.assertTrue(self.audit()['ok'], self.audit()['errors'])

    def test_validation_must_be_independent_of_discovery(self):
        self.init()
        for identity, parents in (('GEO', ()), ('DISC', ('GEO',)), ('VAL-SAME', ('GEO',)), ('TCGA', ()), ('VAL', ('TCGA',))):
            self.artifact(identity, parents)
        self.tree('question', 'add', '--id', 'Q-001', '--statement', '根', '--clarity', '2')
        self.tree('hypothesis', 'add', '--id', 'H-001', '--question', 'Q-001', '--statement', 's', '--prediction', 'p',
                  '--origin', 'ai', '--derived-from', 'DISC')
        code, out = self.tree('hypothesis', 'set', '--id', 'H-001', '--validated-on', 'DISC')
        self.assertIn('not independent', out['error'])
        code, out = self.tree('hypothesis', 'set', '--id', 'H-001', '--validated-on', 'VAL-SAME')
        self.assertIn('share upstream', out['error'])
        self.assertEqual(self.tree('hypothesis', 'set', '--id', 'H-001', '--validated-on', 'VAL')[0], 0)
        self.assertTrue(self.audit()['ok'], self.audit()['errors'])

    def test_intent_brief_must_precede_runs_and_stay_unchanged(self):
        self.init()
        self.tree('question', 'add', '--id', 'Q-001', '--statement', '根', '--clarity', '2')
        current = self.state()
        current['tasks'] = [{'id': 'T-1', 'status': 'todo', 'inputs': [], 'outputs': []}]
        self.save(current)
        self.assertEqual(self.tree('task', 'link', '--id', 'T-1', '--serves', 'Q-001')[0], 0)
        brief = self.root / '_pm/intents/T-1.md'
        brief.parent.mkdir(parents=True)
        brief.write_text('预期：结果 A 意味着…\n', encoding='utf-8')
        self.assertEqual(self.tree('task', 'intent', '--id', 'T-1', '--path', '_pm/intents/T-1.md')[0], 0)
        self.assertTrue(self.audit()['ok'], self.audit()['errors'])
        brief.write_text('事后改写的预期\n', encoding='utf-8')
        self.assertIn('brief changed', ' '.join(self.audit()['errors']))
        brief.write_text('预期：结果 A 意味着…\n', encoding='utf-8')
        run = self.root / 'runs/RUN-1/run.json'
        run.parent.mkdir(parents=True)
        run.write_text(json.dumps({'id': 'RUN-1', 'task': 'T-1', 'started_at': '2000-01-01T00:00:00+00:00'}), encoding='utf-8')
        current = self.state()
        current['runs'] = [{'id': 'RUN-1', 'status': 'running', 'path': 'runs/RUN-1/run.json'}]
        self.save(current)
        self.assertIn('expectations must precede results', ' '.join(self.audit()['errors']))

    # Capability registry
    def test_seed_registry_is_valid_and_searchable(self):
        entries, problems = registry_search.registry()
        self.assertEqual(problems, [])
        self.assertTrue(all(row['status'] == 'candidate' for row in entries.values()))
        hits = registry_search.search(entries, '单细胞 注释', limit=3)
        self.assertIn('kh.scrna-annotation', [h['id'] for h in hits])
        self.assertLessEqual(len(hits), 3)

    def test_project_registry_overrides_and_verified_needs_evidence(self):
        self.init()
        (self.root / '_pm/capabilities.json').write_text(json.dumps({'entries': [
            {'id': 'db.geo', 'kind': 'database', 'summary': '本项目已验证的 GEO 访问', 'tags': ['表达'],
             'access': 'API', 'license': 'NCBI', 'status': 'verified'}]}, ensure_ascii=False), encoding='utf-8')
        entries, problems = registry_search.registry(self.root)
        self.assertEqual(entries['db.geo']['origin'], 'project')
        self.assertTrue(any('verified_at' in p for p in problems))


if __name__ == '__main__':
    unittest.main()
