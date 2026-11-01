"""Regression fixtures for versioned intent, not evidence of scientific validity."""
from argparse import Namespace
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import check_project
import init_project
import record
import research_tree
import run_project


class IntentVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hairw-v431-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'
        init_project.initialize(Namespace(target=str(self.root), name='Synthetic intent fixture',
                                         scale='M', profile='research', dry_run=False,
                                         date='2026-11-01', design=None))
        self.ok(research_tree, 'question', 'add', '--id', 'Q-901', '--statement', 'Fixture only', '--clarity', '2')
        self.ok(research_tree, 'task', 'add', '--id', 'T-901', '--title', 'Fixture work', '--serves', 'Q-901')
        self.write('data/input.txt', 'Synthetic input.\n')
        self.ok(record, 'artifact', '--id', 'A-901', '--path', 'data/input.txt', '--version', 'v1')
        self.write('src/worker.py', 'from pathlib import Path\nimport sys\np = Path(sys.argv[1])\np.parent.mkdir(parents=True, exist_ok=True)\np.write_text("synthetic output")\n')
        self.write('environment.txt', sys.version)

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def state(self):
        return json.loads((self.root / '_pm/project-state.json').read_text(encoding='utf-8'))

    def call(self, module, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = module.main(['--project', str(self.root), *args])
        return code, json.loads(output.getvalue())

    def ok(self, module, *args):
        code, result = self.call(module, *args)
        self.assertEqual(code, 0, result)
        return result

    def intent(self, version):
        path = f'_pm/intents/T-901-{version}.md'
        self.write(path, f'Synthetic expectations {version}; no real research.\n')
        self.ok(research_tree, 'task', 'intent', '--id', 'T-901', '--path', path)
        return self.state()['tasks'][0]['intent']

    def execute(self, identity='RUN-901', **changes):
        output = f'results/{identity}.txt'
        spec = {'id': identity, 'task': 'T-901', 'purpose': 'Synthetic fixture execution', 'stage': 'metadata',
                'inputs': [{'id': 'A-901', 'version': 'v1'}], 'code': ['src/worker.py'],
                'config': '_pm/config.json', 'environment': 'environment.txt',
                'environment_rebuilt': False, 'cache_policy': 'Fresh fixture', 'outputs': [output]}
        spec.update(changes)
        return run_project.run(self.root, spec, [sys.executable, '-B', 'src/worker.py', output])

    def test_intent_update_preserves_old_run_and_binds_new_run(self):
        first = self.intent('v1')
        old_run = self.execute()
        old_path = self.root / 'runs/RUN-901/run.json'
        old_bytes = old_path.read_bytes()
        second = self.intent('v2')
        new_run = self.execute('RUN-902')
        self.assertEqual(old_run['intent_ref'], first)
        self.assertEqual(new_run['intent_ref'], second)
        self.assertEqual(old_path.read_bytes(), old_bytes)
        self.assertEqual(self.state()['tasks'][0]['intent_history'], [first])
        self.assertTrue(check_project.check_project(self.root, verify_hashes=True)['ok'])

    def test_historical_brief_edit_is_detected_and_blocks_execution_without_side_effects(self):
        first = self.intent('v1')
        self.execute()
        self.intent('v2')
        self.write(first['path'], 'Altered historical expectations.\n')
        self.assertFalse(check_project.check_project(self.root)['ok'])
        before = (self.root / '_pm/project-state.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'brief changed'):
            self.execute('RUN-902')
        self.assertEqual((self.root / '_pm/project-state.json').read_bytes(), before)
        self.assertFalse((self.root / 'runs/RUN-902').exists())
        self.assertFalse((self.root / 'results/RUN-902.txt').exists())

    def test_invalid_replacement_cannot_hide_changed_current_brief(self):
        first = self.intent('v1')
        self.write(first['path'], 'Edited after registration.\n')
        self.write('_pm/intents/replacement.md', 'New expectations.\n')
        before = (self.root / '_pm/project-state.json').read_bytes()
        code, result = self.call(research_tree, 'task', 'intent', '--id', 'T-901',
                                 '--path', '_pm/intents/replacement.md')
        self.assertEqual(code, 1, result)
        self.assertEqual((self.root / '_pm/project-state.json').read_bytes(), before)

    def test_same_intent_registration_is_idempotent(self):
        first = self.intent('v1')
        before = (self.root / '_pm/project-state.json').read_bytes()
        self.ok(research_tree, 'task', 'intent', '--id', 'T-901', '--path', first['path'])
        self.assertEqual((self.root / '_pm/project-state.json').read_bytes(), before)

    def test_task_without_registered_intent_is_not_forced_to_backfill(self):
        run = self.execute()
        self.assertNotIn('intent_ref', run)
        self.assertTrue(check_project.check_project(self.root)['ok'])

    def test_run_spec_cannot_select_superseded_intent(self):
        first = self.intent('v1')
        self.intent('v2')
        before = (self.root / '_pm/project-state.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'current registered task intent'):
            self.execute(intent_ref=first)
        self.assertEqual((self.root / '_pm/project-state.json').read_bytes(), before)
        self.assertFalse((self.root / 'runs/RUN-901').exists())
        self.assertFalse((self.root / 'results/RUN-901.txt').exists())

    def legacy_run(self):
        self.intent('v1')
        self.execute()
        path = self.root / 'runs/RUN-901/run.json'
        doc = json.loads(path.read_text(encoding='utf-8'))
        del doc['intent_ref']
        path.write_text(json.dumps(doc), encoding='utf-8')
        return path, doc

    def test_legacy_run_uses_pre_run_history_without_rewriting_record(self):
        path, _ = self.legacy_run()
        old_bytes = path.read_bytes()
        self.intent('v2')
        self.assertTrue(check_project.check_project(self.root)['ok'])
        self.assertEqual(path.read_bytes(), old_bytes)

    def test_legacy_run_without_pre_run_intent_remains_an_error(self):
        path, doc = self.legacy_run()
        doc['started_at'] = '2000-01-01T00:00:00Z'
        path.write_text(json.dumps(doc), encoding='utf-8')
        result = check_project.check_project(self.root)
        self.assertFalse(result['ok'])
        self.assertIn('expectations must precede results', ' '.join(result['errors']))

    def test_explicit_run_reference_cannot_point_to_post_run_intent(self):
        self.intent('v1')
        self.execute()
        second = self.intent('v2')
        path = self.root / 'runs/RUN-901/run.json'
        doc = json.loads(path.read_text(encoding='utf-8'))
        doc['intent_ref'] = second
        path.write_text(json.dumps(doc), encoding='utf-8')
        errors = check_project.check_project(self.root)['errors']
        self.assertIn('expectations must precede results', ' '.join(errors))

    def test_unregistered_reference_is_rejected(self):
        self.intent('v1')
        self.execute()
        path = self.root / 'runs/RUN-901/run.json'
        doc = json.loads(path.read_text(encoding='utf-8'))
        doc['intent_ref']['sha256'] = '0' * 64
        path.write_text(json.dumps(doc), encoding='utf-8')
        errors = check_project.check_project(self.root)['errors']
        self.assertIn('not a registered', ' '.join(errors))

    def test_snapshot_of_actual_intent_is_preserved(self):
        reference = self.intent('v1')
        run = self.execute()
        snap = next(s for s in run['snapshots'] if s['role'] == 'intent')
        self.assertEqual(snap['source'], reference['path'])
        self.assertEqual(snap['sha256'], reference['sha256'])
        self.assertEqual((self.root / snap['snapshot']).read_bytes(), (self.root / reference['path']).read_bytes())

    def test_modified_historical_snapshot_is_detected(self):
        self.intent('v1')
        run = self.execute()
        self.intent('v2')
        snap = next(s for s in run['snapshots'] if s['role'] == 'intent')
        self.write(snap['snapshot'], 'Tampered snapshot.\n')
        self.assertIn('snapshot content changed', ' '.join(check_project.check_project(self.root)['errors']))

    def test_malformed_snapshot_collection_is_reported_without_crash(self):
        self.intent('v1')
        self.execute()
        path = self.root / 'runs/RUN-901/run.json'
        doc = json.loads(path.read_text(encoding='utf-8'))
        doc['snapshots'] = None
        path.write_text(json.dumps(doc), encoding='utf-8')
        self.assertFalse(check_project.check_project(self.root)['ok'])

    def test_same_timestamp_distinct_legacy_versions_are_not_guessed(self):
        with patch('research_tree.now', return_value='2000-01-01T00:00:00Z'):
            self.intent('v1')
            self.intent('v2')
        self.execute()
        path = self.root / 'runs/RUN-901/run.json'
        doc = json.loads(path.read_text(encoding='utf-8'))
        del doc['intent_ref']
        path.write_text(json.dumps(doc), encoding='utf-8')
        self.assertIn('ambiguous legacy intent timing', ' '.join(check_project.check_project(self.root)['errors']))

    def test_timestamps_compare_instants_instead_of_strings(self):
        # 08:30 +08 is earlier than 01:00 UTC despite its lexical ordering.
        with patch('research_tree.now', return_value='2000-01-01T08:30:00+08:00'):
            first = self.intent('v1')
        with patch('run_project.now', return_value='2000-01-01T01:00:00Z'):
            run = self.execute()
        self.assertEqual(run['intent_ref'], first)
        self.assertTrue(check_project.check_project(self.root)['ok'])

    def test_future_or_naive_intent_is_refused_before_run(self):
        with patch('research_tree.now', return_value='2999-01-01T00:00:00Z'):
            self.intent('v1')
        with self.assertRaisesRegex(ValueError, 'expectations must precede results'):
            self.execute()
        self.assertFalse((self.root / 'runs/RUN-901').exists())
        self.write('_pm/intents/naive.md', 'Naive timestamp fixture.\n')
        before = (self.root / '_pm/project-state.json').read_bytes()
        with patch('research_tree.now', return_value='2026-11-01T01:00:00'):
            code, result = self.call(research_tree, 'task', 'intent', '--id', 'T-901', '--path', '_pm/intents/naive.md')
        self.assertEqual(code, 1, result)
        self.assertEqual((self.root / '_pm/project-state.json').read_bytes(), before)


class ExistingFolderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hairw-existing-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'

    def initialize(self, *extra):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = init_project.main(['--target', str(self.root), '--name', 'Synthetic existing project',
                                      '--profile', 'research', '--scale', 'M', *extra])
        return code, json.loads(output.getvalue())

    def test_skip_business_placeholders_preserves_existing_code_and_state(self):
        (self.root / 'scripts').mkdir(parents=True)
        (self.root / 'scripts/original.py').write_bytes(b'# original code\n')
        code, result = self.initialize('--no-research-folders')
        self.assertEqual(code, 0, result)
        self.assertFalse((self.root / 'src').exists())
        self.assertFalse((self.root / 'data/raw/public').exists())
        self.assertEqual((self.root / 'scripts/original.py').read_bytes(), b'# original code\n')
        path = self.root / '_pm/project-state.json'
        state = json.loads(path.read_text(encoding='utf-8'))
        state['layout']['code'] = 'scripts'  # Explicit fixture adaptation, not a migration by the CLI.
        path.write_text(json.dumps(state), encoding='utf-8')
        before = path.read_bytes()
        code, result = self.initialize('--no-research-folders')
        self.assertEqual(code, 0, result)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((self.root / 'src').exists())
        self.assertTrue(check_project.check_project(self.root)['ok'])

    def test_dry_run_skip_has_no_writes_and_default_still_lists_folders(self):
        code, result = self.initialize('--no-research-folders', '--dry-run')
        self.assertEqual(code, 0, result)
        self.assertNotIn('src/README.md', result['would_create'])
        self.assertIn('_pm/research/RESEARCH_PLAN.md', result['would_create'])
        self.assertFalse(self.root.exists())
        code, default = self.initialize('--dry-run')
        self.assertEqual(code, 0, default)
        self.assertIn('src/README.md', default['would_create'])
        self.assertFalse(self.root.exists())


if __name__ == '__main__':
    unittest.main()
