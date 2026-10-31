#!/usr/bin/env python3
"""v4.1 behaviour tests from the real-project pilot: folders, record tool, CP3/template warnings."""
from argparse import Namespace
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import check_project
import init_project
import record


class PilotLessonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hairw-v41-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'

    def init(self, profile='research'):
        return init_project.initialize(Namespace(target=str(self.root), name='v4.1 测试', scale='L',
                                                 profile=profile, dry_run=False, date='2026-10-31', design=None))

    def state(self):
        return json.loads((self.root / '_pm/project-state.json').read_text(encoding='utf-8'))

    def save(self, value):
        (self.root / '_pm/project-state.json').write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def audit(self):
        return check_project.check_project(self.root)

    def record(self, *argv):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = record.main(['--project', str(self.root), *argv])
        return code, json.loads(buffer.getvalue())

    def pass_g1(self):
        current = self.state()
        for gate in current['gates']:
            if gate['id'] == 'G1':
                gate.update(status='conditional', by='负责人', rationale='test', evidence=['_pm/DECISIONS.md'])
        self.save(current)

    def test_research_init_creates_standard_folders(self):
        created = self.init()['created']
        for folder in init_project.RESEARCH_FOLDERS:
            self.assertIn(f'{folder}/README.md', created)
        self.assertTrue(self.audit()['ok'])

    def test_general_init_has_no_research_folders(self):
        created = self.init(profile='general')['created']
        self.assertFalse(any(path.startswith('data/raw') for path in created))

    def test_blank_templates_warn_only_after_g1_started(self):
        self.init()
        self.assertFalse(any('blank template' in w for w in self.audit()['warnings']))
        self.pass_g1()
        warnings = self.audit()['warnings']
        self.assertTrue(any('EVIDENCE_MAP' in w and 'blank template' in w for w in warnings))
        self.assertTrue(any('NARRATIVE' in w and 'blank template' in w for w in warnings))

    def test_filled_documents_clear_template_warning(self):
        self.init()
        self.pass_g1()
        for relative in ('references/EVIDENCE_MAP.md', 'manuscript/NARRATIVE.md'):
            path = self.root / relative
            path.write_text(path.read_text(encoding='utf-8') +
                            '\n| 已确立 | DFU 组织存在炎症细胞浸润 | 观察性 | REF-001 |\n', encoding='utf-8')
        self.assertFalse(any('blank template' in w for w in self.audit()['warnings']))

    def test_route_chosen_without_cp3_warns_until_recorded(self):
        self.init()
        current = self.state()
        current['questions'] = [{'id': 'Q-001', 'statement': '根', 'clarity': 2, 'status': 'open'}]
        current['hypotheses'] = [{'id': 'H-001', 'question': 'Q-001', 'statement': 'x', 'origin': 'ai',
                                  'predictions': ['p'], 'status': 'prioritized'}]
        self.save(current)
        self.assertTrue(any('CP3' in w for w in self.audit()['warnings']))
        (self.root / '_pm/reviews').mkdir(parents=True, exist_ok=True)
        code, out = self.record('decision', '--id', 'D-001', '--title', 'CP3 跳过', '--status', 'adopted',
                                '--checkpoint', 'CP3', '--skipped', '--rationale', '只有两个显而易见的备选，附竞争解释表',
                                '--by', '负责人', '--authorization', '会话中确认')
        self.assertEqual(code, 0, out)
        self.assertFalse(any('CP3' in w for w in self.audit()['warnings']))

    def test_unregistered_run_folder_warns_and_triggers_cp3(self):
        # The pilot ran formal analyses outside run_project.py; the checker must still notice.
        self.init()
        (self.root / 'runs/RUN-X-001').mkdir(parents=True)
        warnings = self.audit()['warnings']
        self.assertTrue(any('not registered' in w and 'RUN-X-001' in w for w in warnings))
        self.assertTrue(any('CP3' in w for w in warnings))

    def test_skipped_checkpoint_needs_rationale_and_adopted_needs_authority(self):
        self.init()
        code, out = self.record('decision', '--id', 'D-001', '--title', 't', '--status', 'proposed',
                                '--checkpoint', 'CP3', '--skipped')
        self.assertEqual(code, 1)
        self.assertIn('rationale', out['error'])
        code, out = self.record('decision', '--id', 'D-001', '--title', 't', '--status', 'adopted')
        self.assertEqual(code, 1)
        self.assertIn('authorization', out['error'])

    def test_record_artifact_hashes_and_refuses_duplicates(self):
        self.init()
        path = self.root / 'results/table.csv'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('a,b\n1,2\n', encoding='utf-8')
        self.assertEqual(self.record('artifact', '--id', 'RES-001', '--path', 'results/table.csv', '--version', 'v1')[0], 0)
        self.assertEqual(self.state()['artifacts'][0]['sha256'], check_project.hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(self.record('artifact', '--id', 'RES-001', '--path', 'results/table.csv', '--version', 'v2')[0], 1)
        self.assertTrue(check_project.check_project(self.root, verify_hashes=True)['ok'])

    def test_record_finding_requires_evidence_file(self):
        self.init()
        (self.root / 'results').mkdir(exist_ok=True)
        (self.root / 'results/table.csv').write_text('x\n1\n', encoding='utf-8')
        self.assertEqual(self.record('artifact', '--id', 'RES-001', '--path', 'results/table.csv',
                                     '--version', 'v1')[0], 0)
        code, out = self.record('finding', '--id', 'F-001', '--title', 't', '--observation', 'o',
                                '--interpretation', 'i', '--by', 'AI', '--evidence', '_pm/FINDINGS.md',
                                '--input', 'RES-404')
        self.assertIn('Register these artifacts', out['error'])
        code, out = self.record('finding', '--id', 'F-001', '--title', 't', '--observation', 'o',
                                '--interpretation', 'i', '--by', 'AI', '--evidence', 'missing.md',
                                '--input', 'RES-001')
        self.assertEqual(code, 1)
        evidence = self.root / '_pm/FINDINGS.md'
        code, out = self.record('finding', '--id', 'F-001', '--title', 't', '--observation', 'o',
                                '--interpretation', 'i', '--by', 'AI', '--evidence', '_pm/FINDINGS.md',
                                '--input', 'RES-001')
        self.assertEqual(code, 0, out)
        self.assertTrue(evidence.is_file())
        self.assertEqual(self.state()['findings'][0]['inputs'], [{'id': 'RES-001', 'version': 'v1'}])


if __name__ == '__main__':
    unittest.main()
