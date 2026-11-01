#!/usr/bin/env python3
"""Synthetic regressions for observed CP3 boundary errors and transactional task creation."""
from argparse import Namespace
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

import check_project
import init_project
import record
import research_tree
import run_project


class StageAndTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hairw-v42-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'
        init_project.initialize(Namespace(target=str(self.root), name='Synthetic metadata probe', scale='L',
                                         profile='research', dry_run=False, date='2026-11-01', design=None))
        self.call(research_tree, 'question', 'add', '--id', 'Q-901', '--statement', 'Identity feasibility',
                  '--clarity', '2')

    def call(self, tool, *argv):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = tool.main(['--project', str(self.root), *argv])
        return code, json.loads(buffer.getvalue())

    def state_bytes(self):
        return (self.root / '_pm/project-state.json').read_bytes()

    def state(self):
        return json.loads(self.state_bytes())

    def cp3_warning(self):
        return any('CP3' in w for w in check_project.check_project(self.root)['warnings'])

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def register_input(self):
        self.write('references/identity.json', '{"donor":"synthetic-1"}\n')
        code, out = self.call(record, 'artifact', '--id', 'META-901', '--path', 'references/identity.json',
                              '--version', 'v1')
        self.assertEqual(code, 0, out)

    def run_spec(self):
        self.register_input()
        self.write('src/probe.py', 'from pathlib import Path\nimport sys\n'
                   'Path(sys.argv[1]).write_text(Path("references/identity.json").read_text())\n')
        self.write('_pm/probe-config.json', '{}\n')
        self.write('environment.txt', 'Synthetic test: ' + sys.version)
        return {'id': 'RUN-901', 'purpose': 'synthetic metadata-only copy',
                'inputs': [{'id': 'META-901', 'version': 'v1'}], 'code': ['src/probe.py'],
                'config': '_pm/probe-config.json', 'environment': 'environment.txt',
                'environment_rebuilt': False, 'cache_policy': 'fresh fixture; no cache',
                'outputs': ['results/probe-901.json']}

    def execute(self, stage='metadata', legacy=False):
        spec = self.run_spec()
        if not legacy:
            spec['stage'] = stage
        result = run_project.run(self.root, spec, [sys.executable, '-B', 'src/probe.py', spec['outputs'][0]])
        self.assertEqual(result['status'], 'succeeded', result)
        self.assertTrue(check_project.check_project(self.root)['ok'])
        return result

    def choose_hypothesis(self):
        code, out = self.call(research_tree, 'hypothesis', 'add', '--id', 'H-901', '--question', 'Q-901',
                              '--statement', 'Synthetic hypothesis', '--prediction', 'Synthetic prediction',
                              '--origin', 'ai', '--status', 'prioritized')
        self.assertEqual(code, 0, out)

    def test_metadata_run_persists_stage_and_defers_cp3(self):
        result = self.execute()
        self.assertEqual(result['stage'], 'metadata')
        stored = json.loads((self.root / 'runs/RUN-901/run.json').read_text(encoding='utf-8'))
        self.assertEqual(stored['stage'], 'metadata')
        self.assertFalse(self.cp3_warning())

    def test_analysis_run_triggers_cp3(self):
        self.execute(stage='analysis')
        self.assertTrue(self.cp3_warning())

    def test_validation_run_triggers_cp3(self):
        self.execute(stage='validation')
        self.assertTrue(self.cp3_warning())

    def test_legacy_run_is_conservative_despite_metadata_purpose(self):
        result = self.execute(legacy=True)
        self.assertNotIn('stage', result)
        self.assertTrue(self.cp3_warning())

    def test_metadata_does_not_hide_selected_hypothesis(self):
        self.execute()
        self.choose_hypothesis()
        self.assertTrue(self.cp3_warning())

    def test_metadata_does_not_hide_g2_start(self):
        self.execute()
        state = self.state()
        gate = next(g for g in state['gates'] if g['id'] == 'G2')
        gate.update(status='conditional', by='synthetic harness', rationale='fixture only',
                    evidence=['references/identity.json'])
        (self.root / '_pm/project-state.json').write_text(json.dumps(state), encoding='utf-8')
        self.assertTrue(self.cp3_warning())

    def test_proposed_cp3_does_not_clear_warning_but_adopted_skip_does(self):
        self.choose_hypothesis()
        code, out = self.call(record, 'decision', '--id', 'D-901', '--title', 'Proposal only',
                              '--checkpoint', 'CP3')
        self.assertEqual(code, 0, out)
        self.assertTrue(self.cp3_warning())
        code, out = self.call(record, 'decision', '--id', 'D-902', '--title', 'Synthetic skip',
                              '--checkpoint', 'CP3', '--skipped', '--rationale', 'Synthetic limited alternatives',
                              '--status', 'adopted', '--by', 'synthetic harness',
                              '--authorization', 'Automated fixture, no human approval inferred')
        self.assertEqual(code, 0, out)
        self.assertFalse(self.cp3_warning())

    def test_bad_stage_is_rejected_before_any_run_or_output(self):
        spec = self.run_spec()
        before = self.state_bytes()
        for invalid in ('unknown', '', None, [], 1):
            with self.subTest(stage=invalid):
                spec['stage'] = invalid
                with self.assertRaisesRegex(ValueError, 'stage must be'):
                    run_project.run(self.root, spec, [sys.executable, '-c', 'raise SystemExit(99)'])
                self.assertEqual(self.state_bytes(), before)
                self.assertFalse((self.root / 'runs/RUN-901').exists())
                self.assertFalse((self.root / spec['outputs'][0]).exists())

    def test_checker_rejects_tampered_stage(self):
        self.execute()
        path = self.root / 'runs/RUN-901/run.json'
        doc = json.loads(path.read_text(encoding='utf-8'))
        doc['stage'] = 'unknown'
        path.write_text(json.dumps(doc), encoding='utf-8')
        report = check_project.check_project(self.root)
        self.assertFalse(report['ok'])
        self.assertTrue(any('invalid run stage' in e for e in report['errors']))
        self.assertTrue(self.cp3_warning())

    def test_task_add_versions_inputs_and_retains_intent_support(self):
        self.register_input()
        code, out = self.call(research_tree, 'task', 'add', '--id', 'T-901', '--title', 'Identity check',
                              '--serves', 'Q-901', '--input', 'META-901@v1')
        self.assertEqual(code, 0, out)
        row = next(t for t in self.state()['tasks'] if t['id'] == 'T-901')
        self.assertEqual(row['status'], 'todo')
        self.assertEqual(row['outputs'], [])
        self.assertEqual(row['inputs'], [{'id': 'META-901', 'version': 'v1'}])
        self.assertEqual(row['serves'], ['Q-901'])
        self.write('_pm/intents/T-901.md', 'Synthetic purpose and stop condition.\n')
        code, out = self.call(research_tree, 'task', 'intent', '--id', 'T-901', '--path', '_pm/intents/T-901.md')
        self.assertEqual(code, 0, out)
        self.assertTrue(check_project.check_project(self.root, verify_hashes=True)['ok'])

    def test_invalid_task_add_is_transactional(self):
        self.register_input()
        for extras in (['--serves', 'Q-404'], ['--input', 'META-901@v2'], ['--input', 'META-404@v1'],
                       ['--input', 'META-901'], ['--input', 'META-901@v1', '--input', 'META-901@v1']):
            with self.subTest(extras=extras):
                before = self.state_bytes()
                code, out = self.call(research_tree, 'task', 'add', '--id', 'T-901', '--title', 'Synthetic', *extras)
                self.assertEqual(code, 1, out)
                self.assertEqual(self.state_bytes(), before)

    def test_duplicate_task_cannot_overwrite(self):
        code, out = self.call(research_tree, 'task', 'add', '--id', 'T-901', '--title', 'First', '--serves', 'Q-901')
        self.assertEqual(code, 0, out)
        before = self.state_bytes()
        code, out = self.call(research_tree, 'task', 'add', '--id', 'T-901', '--title', 'Second')
        self.assertEqual(code, 1, out)
        self.assertEqual(before, self.state_bytes())


if __name__ == '__main__':
    unittest.main()
