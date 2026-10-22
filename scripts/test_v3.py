"""Synthetic behavior tests. All approvals/evidence here are fixtures, never real research."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import build_release
import archive_artifacts
import check_project
import init_project
import manage_change
import project_io
import render_review
import run_project
import verify_reproduction
import test_tools


class V3Tests(unittest.TestCase):
    args = test_tools.ProjectToolsTests.args
    init = test_tools.ProjectToolsTests.init
    write = test_tools.ProjectToolsTests.write
    save_state = test_tools.ProjectToolsTests.save_state
    audit = test_tools.ProjectToolsTests.audit

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='blueprint-v3-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'project'

    def fixture(self):
        current = test_tools.ProjectToolsTests.fixture(self)
        current.update(schema_version=2, layout={'runs': 'runs', 'releases': 'releases', 'review': 'review'})
        for key in ('findings', 'decisions', 'changes', 'claims', 'risks', 'review_items', 'runs', 'reproductions'):
            current[key] = []
        self.write('data/source.csv', '[1,2,3]\n')
        self.write('results/model.json', '{"sum":6}\n')
        self.write('src/main.py', 'import json, pathlib, sys\np = pathlib.Path(sys.argv[1]); p.parent.mkdir(parents=True, exist_ok=True)\np.write_text(json.dumps({"sum":sum(json.loads(pathlib.Path("data/source.csv").read_text()))}))\nprint("ACTUAL_EXECUTION")\n')
        self.write('analysis.json', '{"method":"sum"}\n')
        self.write('environment.txt', 'Synthetic test environment: ' + sys.version)
        self.write('_pm/reviews/requirements.md', 'SYNTHETIC TEST ONLY, no actual journal or author approval.\n')
        self.write('_pm/FINDINGS.md', 'F-1: synthetic observation, not a research finding.\n')
        self.write('_pm/DECISIONS.md', 'D-1: test harness selected a sum fixture.\n')
        for a in current['artifacts']:
            a['sha256'] = project_io.digest(self.root / a['path'])
        current['findings'] = [{'id':'F-1','title':'合成数据求和','status':'observed','observed_at':project_io.now(),
                                'by':'synthetic test harness','observation':'1+2+3=6','interpretation':'仅验证工具链',
                                'record':'_pm/FINDINGS.md','evidence':['results/model.json'],
                                'inputs':[{'id':'DATA','version':'v1'}],'decisions':['D-1'],'changes':[]}]
        current['decisions'] = [{'id':'D-1','title':'采用求和示例','status':'adopted','record':'_pm/DECISIONS.md',
                                 'findings':['F-1'],'by':'synthetic test harness','decided_at':project_io.now(),
                                 'authorization':'automated fixture only; no human approval inferred','evidence':['_pm/DECISIONS.md']}]
        current['claims'] = [{'id':'CL-1','statement':'合成数据之和为6','status':'supported','strength':'仅限此合成数据',
                              'results':[{'id':'RESULT','version':'v1'}],'locations':['manuscript.md'],'findings':['F-1'],
                              'evidence':['results/model.json']}]
        current['review_items'] = [{'id':'RV-1','title':'示例验证范围','status':'accepted','question':'是否仅用于工具验证？',
                                    'recommendation':'是','alternatives':'不运行','consequences':'不产生科学结论',
                                    'inputs':[{'id':'TEXT','version':'v1'}],'evidence':['_pm/reviews/requirements.md'],
                                    'by':'synthetic test harness','response':'fixture acceptance only','responded_at':project_io.now(), 'blocking':True}]
        current['risks'] = [{'id':'RISK-1','title':'误用合成示例','status':'mitigated','impact':'错误推断真实研究通过',
                             'next_action':'保持合成示例标签','owner':'synthetic test harness'}]
        self.save_state(current)
        self.assertTrue(self.audit(verify_hashes=True)['ok'], self.audit())
        return current

    def run_spec(self, identity='RUN-1'):
        return {'id':identity,'purpose':'synthetic end-to-end test','cache_policy':'fresh output; no result cache',
                'environment_rebuilt':False,'inputs':[{'id':'DATA','version':'v1'}], 'code':['src/main.py'],
                'config':'analysis.json','environment':'environment.txt','outputs':[f'run-output/{identity}/result.json']}

    def execute(self, identity='RUN-1', command=None, timeout=None):
        spec = self.run_spec(identity)
        return run_project.run(self.root, spec, command or [sys.executable, '-B', 'src/main.py', spec['outputs'][0]], timeout)

    def repro_spec(self, identity='REP-1', run='RUN-1', scope='full'):
        return {'id':identity,'title':'synthetic sum rerun','run':run,'scope':scope,'required':True,
                'inputs':[{'id':'DATA','version':'v1'},{'id':'RESULT','version':'v1'}],
                'by':'synthetic test harness','rationale':'compare actual sum with fixture baseline',
                'comparisons':[{'expected':'results/model.json','actual':f'run-output/{run}/result.json',
                                'mode':'json_numeric','atol':0,'rtol':0}], 'limitations':'Synthetic sum only; not independent replication'}

    def reproduced(self, scope='full'):
        self.execute()
        return verify_reproduction.verify(self.root, self.repro_spec(scope=scope))

    def release_spec(self, identity='SUB-1'):
        return {'id':identity,'title':'合成项目材料包','journal':'SYNTHETIC TEST ONLY','stage':'tool-test',
                'requirements_record':'_pm/reviews/requirements.md', 'required_gates':['G3'],
                'required_artifacts':['RESULT','TEXT'],'critical_results':['RESULT'],'required_reproductions':['REP-1'],
                'files':[{'artifact':'TEXT','version':'v1','destination':'upload/manuscript.md'},
                         {'artifact':'RESULT','version':'v1','destination':'internal_review/result.json'}],
                'confirmations':[{'id':k,'status':'not_applicable','by':'synthetic test harness',
                                   'rationale':'synthetic fixture, no real submission','evidence':['_pm/reviews/requirements.md']}
                                  for k in ('authors','declarations','journal_requirements','cross_document_consistency')]}

    def open_change(self):
        return manage_change.open_change(self.root, {'id':'CH-1','title':'核查输入','reason':'synthetic scenario','sources':['DATA']})

    def test_new_state_progressive_layout(self):
        self.init()
        current = project_io.state(self.root)
        self.assertEqual(current['schema_version'], 2)
        self.assertFalse((self.root / 'data').exists())
        self.assertTrue((self.root / 'README.md').is_file())

    def test_existing_schema1_preserved(self):
        current = test_tools.ProjectToolsTests.fixture(self)
        current['project']['name'] = '测试项目'
        self.save_state(current)
        before = (self.root / '_pm/project-state.json').read_bytes()
        self.init(profile='research')
        self.assertEqual(before, (self.root / '_pm/project-state.json').read_bytes())

    def test_malformed_extensions_fail_closed(self):
        original = self.fixture()
        for field in ('findings','decisions','changes','claims','risks','review_items','runs','reproductions'):
            for value in (None, {}, [{'id':'BAD','status':[]}], [{'id':'BAD'}]):
                with self.subTest(field=field, value=value):
                    current = copy.deepcopy(original); current[field] = value
                    self.save_state(current)
                    self.assertFalse(self.audit()['ok'])

    def test_adopted_decision_needs_authorization(self):
        current = self.fixture(); del current['decisions'][0]['authorization']; self.save_state(current)
        self.assertFalse(self.audit()['ok'])

    def test_missing_finding_evidence(self):
        current = self.fixture(); current['findings'][0]['evidence'] = ['absent.md']; self.save_state(current)
        self.assertFalse(self.audit()['ok'])

    def test_change_propagates_all_registered_types(self):
        self.fixture(); self.reproduced(); change = self.open_change()
        items = {(i['kind'],i['id']) for i in change['items']}
        for expected in [('artifact','TEXT'),('task','T-TEXT'),('gate','G3'),('reproduction','REP-1'),('claim','CL-1'),('review','RV-1')]:
            self.assertIn(expected, items)
        current = project_io.state(self.root)
        self.assertEqual(current['reproductions'][0]['status'],'stale')
        self.assertEqual(current['claims'][0]['status'],'stale')
        self.assertTrue(self.audit()['ok'], self.audit())

    def test_change_omitted_task_or_gate_detected(self):
        self.fixture(); self.open_change(); original = project_io.state(self.root)
        for kind in ('task','gate','claim','review','artifact'):
            current = copy.deepcopy(original)
            current['changes'][0]['items'] = [i for i in current['changes'][0]['items'] if i['kind'] != kind]
            self.save_state(current)
            self.assertFalse(self.audit()['ok'], kind)

    def test_pending_change_cannot_close_or_mutate(self):
        self.fixture(); self.open_change(); before = (self.root / '_pm/project-state.json').read_bytes()
        with self.assertRaises(ValueError): manage_change.close_change(self.root,'CH-1','test harness','not resolved')
        self.assertEqual(before, (self.root / '_pm/project-state.json').read_bytes())

    def test_explicit_unchanged_closure_and_history(self):
        original = self.fixture(); self.open_change(); current = project_io.state(self.root)
        for key in ('artifacts','tasks','gates','claims','review_items'): current[key] = original[key]
        for item in current['changes'][0]['items']:
            item.update(status='unchanged', rationale='synthetic no-op verified', evidence=['_pm/reviews/requirements.md'])
        self.save_state(current)
        closed = manage_change.close_change(self.root,'CH-1','synthetic test harness','all impacts verified unchanged')
        self.assertEqual(closed['status'],'closed')
        self.assertTrue(self.audit()['ok'])

    def test_run_executes_and_snapshots(self):
        self.fixture(); result = self.execute()
        self.assertEqual(result['status'],'succeeded', result)
        self.assertIn('ACTUAL_EXECUTION',(self.root / result['stdout']).read_text())
        self.assertEqual(len(result['snapshots']),3)
        self.assertTrue(self.audit()['ok'],self.audit())

    def test_run_rejects_existing_outputs_and_ids(self):
        self.fixture(); self.execute()
        with self.assertRaises(ValueError): self.execute()
        spec = self.run_spec('RUN-2'); spec['outputs'] = self.run_spec()['outputs']
        with self.assertRaises(ValueError): run_project.run(self.root,spec,[sys.executable,'-c','pass'])

    def test_failed_run_keeps_logs(self):
        self.fixture(); result = self.execute(command=[sys.executable,'-c','import sys; print("failed"); sys.exit(7)'])
        self.assertEqual(result['status'],'failed'); self.assertEqual(result['returncode'],7)
        with self.assertRaises(ValueError): verify_reproduction.verify(self.root,self.repro_spec())

    def test_timeout_keeps_record(self):
        self.fixture(); result = self.execute(command=[sys.executable,'-c','import time; time.sleep(2)'], timeout=0.1)
        self.assertEqual(result['status'],'timed_out')
        self.assertIsNotNone(result['ended_at'])

    def test_deleted_input_recorded_as_failed(self):
        self.fixture(); result = self.execute(command=[sys.executable,'-c','import pathlib; pathlib.Path("data/source.csv").unlink()'])
        self.assertEqual(result['status'],'failed'); self.assertTrue(result['integrity_issues'])
        self.assertEqual(project_io.state(self.root)['runs'][0]['status'],'failed')

    def test_snapshot_failure_preserved(self):
        self.fixture()
        with patch.object(run_project.shutil,'copyfile',side_effect=OSError('copy failed')):
            result = self.execute()
        self.assertEqual(result['status'],'failed'); self.assertIn('copy failed',result['error'])
        self.assertEqual(project_io.state(self.root)['runs'][0]['status'],'failed')

    def test_actual_reproduction_pass(self):
        self.fixture(); result = self.reproduced()
        self.assertEqual(result['status'],'pass'); self.assertTrue(self.audit()['ok'],self.audit())
        with self.assertRaises(ValueError): verify_reproduction.verify(self.root,self.repro_spec())

    def test_numeric_semantics_and_tolerance(self):
        equal = verify_reproduction.numeric_equal
        self.assertTrue(equal({'v':[1,2]}, {'v':[1.01,2]}, .02, 0))
        for a,b in [(True,1),(float('nan'),float('nan')),(float('inf'),float('inf')),([1],[1,2]),({'x':1},{'y':1})]:
            self.assertFalse(equal(a,b,0,0))

    def test_failed_comparison_retained(self):
        self.fixture(); self.write('results/model.json','{"sum":7}')
        current = project_io.state(self.root); current['artifacts'][1]['sha256'] = project_io.digest(self.root/'results/model.json'); self.save_state(current)
        result = self.reproduced(); self.assertEqual(result['status'],'fail')
        self.assertEqual(project_io.state(self.root)['reproductions'][0]['status'],'fail')

    def test_same_file_comparison_rejected(self):
        self.fixture(); self.execute(); spec = self.repro_spec(); spec['comparisons'][0]['expected'] = spec['comparisons'][0]['actual']
        with self.assertRaises(ValueError): verify_reproduction.verify(self.root,spec)

    def test_source_change_invalidates_reproduction(self):
        self.fixture(); self.reproduced(); self.write('analysis.json','{"method":"different"}')
        report = self.audit(); self.assertIn('REP-1',report['governance']['invalid_or_pending_reproductions'])
        with self.assertRaises(ValueError): build_release.package(self.root,self.release_spec(),'ready')

    def test_snapshot_tampering_is_error(self):
        self.fixture(); self.reproduced()
        doc = project_io.load(self.root/'runs/RUN-1/run.json'); self.write(doc['snapshots'][0]['snapshot'],'tampered')
        self.assertFalse(self.audit()['ok'])

    def test_partial_not_enough_for_research_ready(self):
        self.fixture(); self.reproduced('partial')
        with self.assertRaises(ValueError): build_release.package(self.root,self.release_spec(),'ready')

    def test_ready_release_is_immutable_and_verifiable(self):
        self.fixture(); self.reproduced(); result = build_release.package(self.root,self.release_spec(),'ready')
        self.assertFalse(result['blockers']); self.assertTrue(build_release.verify_package(self.root,'releases/SUB-1')['ok'])
        self.assertTrue((self.root/'releases/SUB-1/internal_review/requirements/requirements.md').is_file())
        with self.assertRaises(ValueError): build_release.package(self.root,self.release_spec(),'draft')

    def test_draft_preserves_blockers_ready_refuses(self):
        self.fixture(); spec = self.release_spec(); result = build_release.package(self.root,spec,'draft')
        self.assertTrue(result['blockers']); spec['id']='SUB-2'
        with self.assertRaises(ValueError): build_release.package(self.root,spec,'ready')
        self.assertFalse((self.root/'releases/SUB-2').exists())

    def test_missing_confirmation_blocks_ready(self):
        self.fixture(); self.reproduced(); spec = self.release_spec(); spec['confirmations']=[]
        with self.assertRaises(ValueError): build_release.package(self.root,spec,'ready')

    def test_open_change_blocks_ready(self):
        self.fixture(); self.reproduced(); self.open_change()
        with self.assertRaises(ValueError): build_release.package(self.root,self.release_spec(),'ready')

    def test_package_damage_and_current_drift_distinguished(self):
        self.fixture(); self.reproduced(); build_release.package(self.root,self.release_spec(),'ready')
        self.write('manuscript.md','new source')
        self.assertTrue(build_release.verify_package(self.root,'releases/SUB-1')['ok'])
        current = build_release.verify_package(self.root,'releases/SUB-1',True)
        self.assertTrue(current['package_intact']); self.assertIn('manuscript.md',current['source_drift'])
        self.write('releases/SUB-1/upload/manuscript.md','damaged')
        self.assertFalse(build_release.verify_package(self.root,'releases/SUB-1')['package_intact'])

    def test_racing_existing_release_is_never_deleted(self):
        self.fixture(); spec=self.release_spec(); actual_mkdir=Path.mkdir
        target=self.root/'releases/SUB-1'
        def racing(path,*args,**kwargs):
            if path == target:
                actual_mkdir(path,parents=True,exist_ok=True)
                (path/'unrelated.txt').write_text('preserve')
                raise FileExistsError('racing creator')
            return actual_mkdir(path,*args,**kwargs)
        with patch.object(Path,'mkdir',racing):
            with self.assertRaises(FileExistsError): build_release.package(self.root,spec,'draft')
        self.assertEqual((target/'unrelated.txt').read_text(),'preserve')

    def test_general_release_has_no_research_gate_requirement(self):
        current = self.fixture(); current['project']['profile']='general'; self.save_state(current)
        spec=self.release_spec(); spec.update(recipient='synthetic client', required_gates=[],critical_results=[],required_reproductions=[])
        spec['confirmations']=[dict(spec['confirmations'][0],id=k) for k in ('delivery_authorization','delivery_requirements','cross_document_consistency')]
        self.assertFalse(build_release.package(self.root,spec,'ready')['blockers'])

    def test_review_offline_escaped_six_views(self):
        current=self.fixture(); current['project']['name']='<script>alert(1)</script>'; self.save_state(current)
        result=render_review.render(self.root); document=Path(result['view']).read_text(encoding='utf-8')
        self.assertIn('&lt;script&gt;',document); self.assertNotIn('<script>alert(1)</script>',document)
        self.assertEqual(document.count('<section id='),6)
        self.assertNotIn('<script src=',document); self.assertTrue(render_review.render(self.root,check=True)['ok'])

    def test_review_detects_code_and_evidence_drift(self):
        self.fixture(); self.reproduced(); render_review.render(self.root); self.write('src/main.py','changed')
        result=render_review.render(self.root,check=True)
        self.assertFalse(result['ok']); self.assertIn('src/main.py',result['changed_inputs'])

    def test_review_baseline_and_no_overwrite_unrelated_view(self):
        self.fixture(); render_review.render(self.root)
        self.write('_pm/reviews/baseline.json',(self.root/'review/snapshot.json').read_text(encoding='utf-8'))
        self.write('_pm/STATUS.md','context changed')
        render_review.render(self.root,baseline='_pm/reviews/baseline.json')
        self.assertIn('STATUS.md',(self.root/'review/index.html').read_text(encoding='utf-8'))
        self.write('review/index.html','unrelated document')
        with self.assertRaises(ValueError): render_review.render(self.root)
        self.assertEqual((self.root/'review/index.html').read_text(),'unrelated document')

    def test_paths_cannot_escape(self):
        for relative in ('../outside','C:/outside','/tmp/out','data\\x','x:y','a/../../x'):
            with self.subTest(path=relative):
                with self.assertRaises(ValueError): project_io.local(self.root,relative)

    def archive_spec(self):
        return {'id':'ARCH-1','artifacts':['DATA'],'by':'synthetic test harness', 'reason':'synthetic retirement',
                'disposition':'out_of_scope','evidence':['_pm/reviews/requirements.md'],'change':'CH-1'}

    def test_archive_preserves_originals_and_blocks_new_input(self):
        self.fixture(); self.open_change(); original=(self.root/'data/source.csv').read_bytes()
        result=archive_artifacts.archive(self.root,self.archive_spec())
        self.assertTrue(result['originals_preserved'])
        self.assertEqual(original,(self.root/'data/source.csv').read_bytes())
        self.assertEqual(project_io.state(self.root)['artifacts'][0]['lifecycle'],'retired')
        self.assertTrue(self.audit(verify_hashes=True)['ok'],self.audit())
        with self.assertRaises(ValueError): self.execute()

    def test_archive_requires_impact_handling(self):
        self.fixture(); before=(self.root/'_pm/project-state.json').read_bytes(); spec=self.archive_spec(); del spec['change']
        with self.assertRaises(ValueError): archive_artifacts.archive(self.root,spec)
        self.assertEqual(before,(self.root/'_pm/project-state.json').read_bytes())
        self.assertFalse((self.root/'archive/retired/ARCH-1').exists())

    def test_archive_is_immutable_and_tamper_detected(self):
        self.fixture(); self.open_change(); archive_artifacts.archive(self.root,self.archive_spec())
        with self.assertRaises(ValueError): archive_artifacts.archive(self.root,self.archive_spec())
        retirement=project_io.state(self.root)['artifacts'][0]['retirement']; self.write(retirement['snapshot'],'damaged')
        self.assertFalse(self.audit(verify_hashes=True)['ok'])

    def test_retired_artifact_cannot_enter_draft_release(self):
        self.fixture(); self.open_change(); archive_artifacts.archive(self.root,self.archive_spec())
        spec=self.release_spec(); spec['files']=[{'artifact':'DATA','version':'v1','destination':'upload/source.csv'}]
        with self.assertRaises(ValueError): build_release.package(self.root,spec,'draft')

    def test_full_reproduction_coverage_is_actual_comparison(self):
        current=self.fixture(); self.write('results/fig.svg','{"sum":6}')
        current['artifacts'][2]['sha256']=project_io.digest(self.root/'results/fig.svg'); self.save_state(current)
        self.execute(); spec=self.repro_spec(); spec['inputs'].append({'id':'FIG','version':'v1'})
        spec['comparisons'][0]['expected']='results/fig.svg'
        self.assertEqual(verify_reproduction.verify(self.root,spec)['status'],'pass')
        with self.assertRaises(ValueError): build_release.package(self.root,self.release_spec(),'ready')

    def test_reproduction_replacement_can_close_change(self):
        self.fixture(); self.reproduced(); self.open_change(); current=project_io.state(self.root)
        for a in current['artifacts']: a['status']='accepted'
        for g in current['gates']: g['status']='pass'
        current['tasks'][0]['status']='done'; current['claims'][0]['status']='supported'; current['review_items'][0]['status']='accepted'
        self.save_state(current)
        self.execute('RUN-2'); verify_reproduction.verify(self.root,self.repro_spec('REP-2','RUN-2'))
        current=project_io.state(self.root)
        for item in current['changes'][0]['items']:
            item.update(status='unchanged',rationale='synthetic no-op reviewed',evidence=['_pm/reviews/requirements.md'])
            if item['kind']=='reproduction': item.update(status='updated',replacement='REP-2',evidence=[current['reproductions'][1]['report']])
        self.save_state(current)
        closed=manage_change.close_change(self.root,'CH-1','synthetic test harness','fresh comparison replaces historical one')
        self.assertEqual(closed['status'],'closed')
        self.assertEqual(project_io.state(self.root)['reproductions'][0]['status'],'stale')


if __name__ == '__main__':
    unittest.main(verbosity=2)
