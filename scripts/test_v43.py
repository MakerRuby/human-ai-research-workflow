"""Observable lifecycle/acceptance behavior; all approvals and data are synthetic fixtures."""
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
import manage_change


class ExecutionAndAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hairw-v43-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'
        init_project.initialize(Namespace(target=str(self.root), name='Synthetic lifecycle test', scale='L',
                                          profile='research', dry_run=False, date='2026-11-01', design=None))
        self.write('_pm/checks/review.md', 'Synthetic evidence only; not a real scientific review.\n')
        self.call(research_tree, 'question', 'add', '--id', 'Q-901', '--statement', 'Synthetic question', '--clarity', '2')

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def state(self):
        return json.loads((self.root / '_pm/project-state.json').read_text(encoding='utf-8'))

    def raw(self):
        return (self.root / '_pm/project-state.json').read_bytes()

    def call(self, module, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = module.main(['--project', str(self.root), *args])
        return code, json.loads(output.getvalue())

    def ok(self, module, *args):
        code, result = self.call(module, *args)
        self.assertEqual(code, 0, result)
        return result

    def refused(self, module, *args):
        before = self.raw()
        code, result = self.call(module, *args)
        self.assertEqual(code, 1, result)
        self.assertEqual(before, self.raw(), result)
        return result

    def proof(self):
        return ['--by', 'synthetic harness', '--rationale', 'Fixture decision, not human approval',
                '--evidence', '_pm/checks/review.md']

    def decision(self, identity='D-901', proposed=False):
        args = ['decision', '--id', identity, '--title', 'Synthetic control']
        if not proposed:
            args += ['--status', 'adopted', '--by', 'synthetic harness',
                     '--authorization', 'Synthetic fixture only, no actual owner approval']
        self.ok(record, *args)

    def task(self, identity='T-901'):
        self.ok(research_tree, 'task', 'add', '--id', identity, '--title', 'Fixture work', '--serves', 'Q-901')
        self.write(f'_pm/intents/{identity}.md', 'Synthetic purpose, bounded output and stop condition.\n')
        self.ok(research_tree, 'task', 'intent', '--id', identity, '--path', f'_pm/intents/{identity}.md')

    def artifact(self):
        self.write('results/result.txt', 'Synthetic result.\n')
        self.ok(record, 'artifact', '--id', 'A-901', '--path', 'results/result.txt', '--version', 'v1')

    def check(self, identity='C-901', status='pass', required=False):
        args = ['check', '--id', identity, '--artifact', 'A-901', '--version', 'v1',
                '--kind', 'professional', '--status', status, *self.proof()]
        if required:
            args.append('--required')
        self.ok(record, *args)

    def accepted(self):
        self.artifact()
        self.check()
        self.ok(record, 'accept', '--id', 'A-901', '--check', 'C-901', *self.proof())

    def stop(self, status='stopped', *extra):
        self.ok(record, 'project', '--status', status, '--decision', 'D-901', *self.proof(), *extra)

    def spec(self, task=None):
        self.artifact()
        self.write('src/marker.py', 'from pathlib import Path\nPath("results/ran.txt").write_text("ran")\n')
        self.write('_pm/config-fixture.json', '{}\n')
        self.write('environment-fixture.txt', sys.version)
        return {'id': 'RUN-901', 'purpose': 'Synthetic marker execution', 'stage': 'metadata',
                'inputs': [{'id': 'A-901', 'version': 'v1'}], 'code': ['src/marker.py'],
                'config': '_pm/config-fixture.json', 'environment': 'environment-fixture.txt',
                'environment_rebuilt': False, 'cache_policy': 'Fresh fixture',
                'outputs': ['results/ran.txt'], **({'task': task} if task else {})}

    def test_accept_links_passed_checks_and_real_acceptance_in_one_commit(self):
        self.accepted()
        current = self.state()
        artifact = next(a for a in current['artifacts'] if a['id'] == 'A-901')
        self.assertEqual(artifact['status'], 'accepted')
        self.assertEqual(artifact['required_checks'], ['C-901'])
        self.assertEqual(artifact['acceptance']['by'], 'synthetic harness')
        self.assertTrue(next(c for c in current['checks'] if c['id'] == 'C-901')['required'])
        self.assertTrue(check_project.check_project(self.root, verify_hashes=True)['ok'])

    def test_unchecked_work_cannot_be_accepted(self):
        self.artifact()
        self.refused(record, 'accept', '--id', 'A-901', *self.proof())

    def test_accept_cannot_hide_a_failed_required_check(self):
        self.artifact()
        self.check()
        self.check('C-902', 'fail', required=True)
        self.refused(record, 'accept', '--id', 'A-901', '--check', 'C-901', *self.proof())

    def test_changed_artifact_cannot_reuse_check(self):
        self.artifact()
        self.check()
        self.write('results/result.txt', 'Changed after review.\n')
        self.refused(record, 'accept', '--id', 'A-901', '--check', 'C-901', *self.proof())

    def test_check_cannot_target_other_version_or_overwrite_evidence(self):
        self.artifact()
        self.refused(record, 'check', '--id', 'C-901', '--artifact', 'A-901', '--version', 'v2',
                     '--kind', 'machine', '--status', 'pass', *self.proof())
        self.check()
        self.refused(record, 'check', '--id', 'C-901', '--artifact', 'A-901', '--version', 'v1',
                     '--kind', 'machine', '--status', 'fail', *self.proof())

    def test_check_needs_actual_local_evidence(self):
        self.artifact()
        self.refused(record, 'check', '--id', 'C-901', '--artifact', 'A-901', '--version', 'v1',
                     '--kind', 'source', '--status', 'pass', '--by', 'fixture', '--rationale', 'fixture',
                     '--evidence', '../outside.txt')

    def test_required_check_cannot_be_waived(self):
        self.artifact()
        self.refused(record, 'check', '--id', 'C-901', '--artifact', 'A-901', '--version', 'v1',
                     '--kind', 'source', '--status', 'waived', '--required', '--waiver-reason', 'fixture',
                     *self.proof())

    def test_check_refuses_unregistered_content_changes(self):
        self.artifact()
        self.write('results/result.txt', 'Different content under the same version.\n')
        self.refused(record, 'check', '--id', 'C-901', '--artifact', 'A-901', '--version', 'v1',
                     '--kind', 'machine', '--status', 'pass', *self.proof())

    def test_nonrequired_check_can_be_explicitly_waived(self):
        self.artifact()
        self.ok(record, 'check', '--id', 'C-901', '--artifact', 'A-901', '--version', 'v1',
                '--kind', 'source', '--status', 'waived', '--waiver-reason', 'Optional fixture check',
                *self.proof())

    def test_done_requires_accepted_output_and_does_not_guess_it(self):
        self.task()
        self.artifact()
        self.refused(research_tree, 'task', 'set', '--id', 'T-901', '--status', 'done',
                     '--output', 'A-901', *self.proof())
        self.check()
        self.ok(record, 'accept', '--id', 'A-901', '--check', 'C-901', *self.proof())
        self.ok(research_tree, 'task', 'set', '--id', 'T-901', '--status', 'done',
                '--output', 'A-901', *self.proof())
        self.assertEqual(next(t for t in self.state()['tasks'] if t['id'] == 'T-901')['status'], 'done')

    def test_stop_freezes_unfinished_work_without_asserting_success(self):
        self.task()
        self.decision()
        self.stop('stopped', '--objective-achieved', 'no')
        current = self.state()
        self.assertIs(current['project']['objective_achieved'], False)
        self.assertEqual(next(t for t in current['tasks'] if t['id'] == 'T-901')['status'], 'stopped')
        self.assertTrue(check_project.check_project(self.root)['ok'])

    def test_output_only_update_retains_its_actual_role_and_evidence(self):
        self.task()
        self.artifact()
        self.ok(research_tree, 'task', 'set', '--id', 'T-901', '--output', 'A-901', *self.proof())
        task = next(t for t in self.state()['tasks'] if t['id'] == 'T-901')
        self.assertEqual(task['status'], 'todo')
        self.assertEqual(task['output_history'][-1]['record']['by'], 'synthetic harness')
        self.assertEqual(task['output_history'][-1]['record']['evidence'], ['_pm/checks/review.md'])

    def test_stop_does_not_change_done_work_or_passed_gates(self):
        self.task()
        self.accepted()
        self.ok(research_tree, 'task', 'set', '--id', 'T-901', '--status', 'done', '--output', 'A-901', *self.proof())
        self.decision()
        current = self.state()
        gate = current['gates'][0]
        gate.update(status='pass', artifacts=['A-901'], checks=['C-901'], by='synthetic harness',
                    rationale='Synthetic scoped gate only', evidence=['_pm/checks/review.md'])
        (self.root / '_pm/project-state.json').write_text(json.dumps(current), encoding='utf-8')
        self.assertTrue(check_project.check_project(self.root)['ok'])
        gates = self.state()['gates']
        self.stop()
        current = self.state()
        self.assertEqual(current['gates'], gates)
        self.assertEqual(next(t for t in current['tasks'] if t['id'] == 'T-901')['status'], 'done')
        self.assertNotIn('objective_achieved', current['project'])

    def test_paused_and_stopped_projects_refuse_actual_execution_before_side_effects(self):
        spec = self.spec()
        self.decision()
        for status in ('paused', 'stopped'):
            with self.subTest(status=status):
                self.stop(status)
                before = self.raw()
                with self.assertRaisesRegex(ValueError, 'Project execution'):
                    run_project.run(self.root, spec, [sys.executable, '-B', 'src/marker.py'])
                self.assertEqual(self.raw(), before)
                self.assertFalse((self.root / 'results/ran.txt').exists())
                self.assertFalse((self.root / 'runs/RUN-901').exists())

    def test_proposal_is_not_authorization_to_stop(self):
        self.decision(proposed=True)
        self.refused(record, 'project', '--status', 'stopped', '--decision', 'D-901', *self.proof())

    def test_old_stop_decision_cannot_be_reused_to_resume(self):
        self.decision()
        self.stop()
        self.refused(record, 'project', '--status', 'active', '--decision', 'D-901', *self.proof())

    def test_project_resumption_does_not_automatically_resume_task(self):
        self.task()
        spec = self.spec('T-901')
        self.decision()
        self.stop()
        self.decision('D-902')
        result = self.ok(record, 'project', '--status', 'active', '--decision', 'D-902', *self.proof())
        self.assertEqual(result['tasks_resumed'], [])
        with self.assertRaisesRegex(ValueError, 'Task execution'):
            run_project.run(self.root, spec, [sys.executable, '-B', 'src/marker.py'])
        self.refused(research_tree, 'task', 'set', '--id', 'T-901', '--status', 'doing',
                     '--decision', 'D-901', *self.proof())
        self.ok(research_tree, 'task', 'set', '--id', 'T-901', '--status', 'doing',
                '--decision', 'D-902', *self.proof())
        result = run_project.run(self.root, spec, [sys.executable, '-B', 'src/marker.py'])
        self.assertEqual(result['status'], 'succeeded', result)
        self.assertEqual((self.root / 'results/ran.txt').read_text(), 'ran')

    def test_controlled_task_state_needs_adopted_decision(self):
        self.task()
        self.refused(research_tree, 'task', 'set', '--id', 'T-901', '--status', 'cancelled', *self.proof())
        self.decision()
        self.ok(research_tree, 'task', 'set', '--id', 'T-901', '--status', 'cancelled',
                '--decision', 'D-901', *self.proof())

    def test_success_requires_an_explicit_assessment(self):
        self.decision()
        self.refused(record, 'project', '--status', 'stopped', '--decision', 'D-901',
                     '--objective-achieved', 'yes', *self.proof())
        self.assertNotIn('objective_achieved', self.state()['project'])

    def test_proposal_can_be_withdrawn_without_manufacturing_adoption(self):
        self.decision(proposed=True)
        self.ok(record, 'decision-set', '--id', 'D-901', '--status', 'withdrawn', *self.proof())
        row = next(d for d in self.state()['decisions'] if d['id'] == 'D-901')
        self.assertEqual(row['status'], 'withdrawn')
        self.assertNotIn('authorization', row)
        self.assertEqual(row['status_history'][0]['status'], 'proposed')
        self.assertTrue(check_project.check_project(self.root)['ok'])

    def test_supersession_keeps_original_adoption(self):
        self.decision()
        self.decision('D-902')
        old = next(d for d in self.state()['decisions'] if d['id'] == 'D-901')
        self.ok(record, 'decision-set', '--id', 'D-901', '--status', 'superseded',
                '--superseded-by', 'D-902', *self.proof())
        row = next(d for d in self.state()['decisions'] if d['id'] == 'D-901')
        self.assertEqual(row['authorization'], old['authorization'])
        self.assertEqual(row['superseded_by'], 'D-902')

    def test_supersession_cannot_use_self_or_an_unadopted_replacement(self):
        self.decision()
        self.decision('D-902', proposed=True)
        for identity in ('D-901', 'D-902', 'D-999'):
            with self.subTest(replacement=identity):
                self.refused(record, 'decision-set', '--id', 'D-901', '--status', 'superseded',
                             '--superseded-by', identity, *self.proof())

    def test_historical_stop_keeps_its_authority_after_valid_supersession(self):
        self.task()
        self.decision()
        self.stop()
        self.decision('D-902')
        self.ok(record, 'project', '--status', 'active', '--decision', 'D-902', *self.proof())
        self.ok(record, 'decision-set', '--id', 'D-901', '--status', 'superseded',
                '--superseded-by', 'D-902', *self.proof())
        self.assertTrue(check_project.check_project(self.root)['ok'])

    def test_old_schema_two_project_needs_no_migration(self):
        self.assertNotIn('execution', self.state()['project'])
        self.assertTrue(check_project.check_project(self.root, verify_hashes=True)['ok'])

    def test_checker_detects_stopped_task_without_control_evidence(self):
        self.task()
        current = self.state()
        next(t for t in current['tasks'] if t['id'] == 'T-901')['status'] = 'stopped'
        (self.root / '_pm/project-state.json').write_text(json.dumps(current), encoding='utf-8')
        report = check_project.check_project(self.root)
        self.assertFalse(report['ok'])
        self.assertTrue(any('T-901.status_record' in e for e in report['errors']))

    def test_input_change_does_not_resume_an_owner_stopped_task(self):
        self.task()
        self.accepted()
        self.ok(research_tree, 'task', 'set', '--id', 'T-901', '--output', 'A-901', *self.proof())
        self.decision()
        self.stop()
        manage_change.open_change(self.root, {'id': 'CH-901', 'title': 'Fixture change',
                                            'reason': 'Fixture input review', 'sources': ['A-901']})
        task = next(t for t in self.state()['tasks'] if t['id'] == 'T-901')
        self.assertEqual(task['status'], 'stopped')
        self.assertEqual(task['pending_input_change'], 'CH-901')
        self.assertTrue(check_project.check_project(self.root)['ok'])

    def test_input_change_reopens_done_task_without_losing_prior_transition(self):
        self.task()
        self.accepted()
        self.ok(research_tree, 'task', 'set', '--id', 'T-901', '--status', 'done', '--output', 'A-901', *self.proof())
        manage_change.open_change(self.root, {'id': 'CH-901', 'title': 'Fixture change',
                                            'reason': 'Fixture input review', 'sources': ['A-901']})
        task = next(t for t in self.state()['tasks'] if t['id'] == 'T-901')
        self.assertEqual(task['status'], 'todo')
        self.assertNotIn('status_record', task)
        self.assertEqual(task['status_history'][-1]['invalidated_by'], 'CH-901')
        self.assertTrue(check_project.check_project(self.root)['ok'])


if __name__ == '__main__':
    unittest.main()
