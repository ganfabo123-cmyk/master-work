"""Audit ingress, unsuccessful paths, pre-filter scores and concurrent writers."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tests.test_retrieval_api as fixtures
from agent_protocol import RetrievalStatus
from dsh_bridge import handle
from manager import load_config
from retrieval import SkillSystem
from runtime_audit import RuntimeAudit
from storage import SnapshotStore


class RuntimeAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT/'config.json')
        cls.base = SnapshotStore(cls.config['data_dir']).read()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = dict(self.config, data_dir=Path(temporary.name)/'data')
        self.snapshot = copy.deepcopy(self.base)
        self.store = SnapshotStore(self.config['data_dir'])
        self.store.publish(self.snapshot)
        self.target = next(iter(self.snapshot['state']['skills']))
        self.provider = fixtures.Provider(self.snapshot['vectors']['entries'][self.target]['vector'])
        self.system = SkillSystem(config=self.config, embedding=self.provider)

    def logs(self, event=None):
        rows = [json.loads(line) for line in self.system.audit.path.read_text(encoding='utf8').splitlines()]
        return [r for r in rows if r['event']==event] if event else rows

    def test_all_ingress_no_trigger_empty_and_hint_have_correlated_scores(self):
        returned, result = self.system.agent_session().handle_messages([
            {'role':'assistant','content':'context'},
            {'type':'user_input','content':' '},
            {'type':'tool/result','content':'compiler error'},
        ])
        self.assertEqual(len(self.logs('trace_received')), 3)
        completed = self.logs('trace_completed')
        self.assertEqual([r['triggered'] for r in completed], [False,True,True])
        self.assertEqual(completed[0]['embedding']['status'], 'measured')
        self.assertEqual(completed[1]['embedding']['reason'], 'empty_text')
        self.assertEqual(len(completed[2]['embedding']['candidates']), 35)
        self.assertEqual(result.status, RetrievalStatus.COMPLETED)
        self.assertEqual(len(returned),4)
        self.assertTrue(self.logs('hint_decision')[0]['generated'])
        self.assertEqual(len({r['batch_id'] for r in self.logs()}),1)
        self.assertTrue(all('local_time' in r for r in self.logs()))

    def test_threshold_empty_keeps_all_raw_scores_and_minimum(self):
        self.provider.vector = [-v for v in self.provider.vector]
        returned,result = self.system.agent_session().handle_messages([{'type':'user_input','content':'q'}])
        self.assertEqual(result.items, [])
        self.assertEqual(len(returned),1)
        complete = self.logs('retrieval_completed')[0]
        self.assertFalse(complete['has_results'])
        self.assertTrue(complete['success'])
        self.assertEqual(complete['embedding']['min_similarity'],.5)
        self.assertEqual(len(complete['embedding']['candidates']),35)
        self.assertLess(complete['embedding']['top_similarity'],.5)
        self.assertTrue(all(not c['passes_min_similarity'] for c in complete['embedding']['candidates']))
        self.assertFalse(self.logs('hint_decision')[0]['generated'])

    def test_tool_result_followed_by_step_end_still_returns_hint(self):
        messages = [
            {'type': 'tool/result', 'message': {'role': 'tool', 'content': [
                {'type': 'text', 'text': 'compiler error'},
            ]}},
            {'type': 'step/end', 'turn': 1, 'step': 1},
        ]
        returned, result = self.system.agent_session().handle_messages(messages)
        self.assertEqual(result.status, RetrievalStatus.COMPLETED)
        self.assertTrue(result.items)
        self.assertEqual(returned[:-1], messages)
        self.assertEqual(returned[-1]['type'], 'user_input')
        decisions = self.logs('trigger_decision')
        self.assertEqual([r['triggered'] for r in decisions], [True, False])
        self.assertEqual(self.logs('hint_decision')[0]['source_trace_id'], decisions[0]['trace_id'])

    def test_later_empty_tool_result_does_not_reuse_previous_hit(self):
        returned, result = self.system.agent_session().handle_messages([
            {'type': 'tool/result', 'content': 'compiler error'},
            {'type': 'tool/result', 'content': ' '},
            {'type': 'step/end', 'turn': 1, 'step': 1},
        ])
        self.assertEqual(result.status, RetrievalStatus.EMPTY_QUERY)
        self.assertEqual(len(returned), 3)
        self.assertFalse(self.logs('hint_decision')[0]['generated'])

    def test_protocol_events_are_logged_without_embedding_envelopes(self):
        messages = [
            {'type': 'assistant/chunk', 'chunk': {'text': str(i)}}
            for i in range(145)
        ] + [
            {'type': 'assistant/message', 'message': {'role': 'assistant', 'content': [
                {'type': 'text', 'text': 'Now compiling'},
            ]}},
            {'type': 'tool/result', 'message': {'role': 'user', 'content': [
                {'type': 'tool-result', 'toolCallId': 'compile', 'content': 'compiler error', 'isError': True},
            ]}},
            {'type': 'step/end', 'turn': 1, 'step': 1},
        ]
        returned, result = self.system.agent_session().handle_messages(messages)
        self.assertEqual(len(self.logs('trace_received')), 148)
        self.assertEqual(len(self.logs('trace_completed')), 148)
        self.assertEqual(self.provider.calls, ['Now compiling', 'compiler error'])
        self.assertEqual(len(self.logs('embedding_started')), 2)
        self.assertEqual(self.logs('trigger_decision')[-2]['event_type'], 'tool_result')
        completed = self.logs('trace_completed')
        self.assertTrue(all(r['embedding']['reason'] == 'no_message_content' for r in completed[:145]))
        self.assertIsNone(completed[-1]['embedding']['top_similarity'])
        self.assertEqual(result.status, RetrievalStatus.COMPLETED)
        self.assertEqual(len(returned), 149)

    def test_embedding_failure_is_logged_even_without_snapshot_commit(self):
        before=(self.store.root/'CURRENT').read_text()
        with patch.object(self.provider,'embed',side_effect=RuntimeError('provider unavailable')):
            with self.assertRaisesRegex(RuntimeError,'provider unavailable'):
                self.system.agent_session().handle_messages(['query'])
        self.assertEqual((self.store.root/'CURRENT').read_text(),before)
        self.assertEqual(len(self.logs('trace_received')),1)
        self.assertTrue(self.logs('trigger_decision')[0]['triggered'])
        error=self.logs('retrieval_failed')[0]
        self.assertEqual(error['embedding']['status'],'failed')
        self.assertIsNone(error['embedding']['top_similarity'])
        self.assertIn('provider unavailable',error['error'])
        self.assertEqual(len(self.logs('messages_failed')),1)

    def test_publish_failure_retains_already_measured_similarity(self):
        with patch.object(self.system.store,'publish',side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):self.system.retrieve('query')
        failure=self.logs('retrieval_failed')[0]
        self.assertEqual(failure['embedding']['status'],'measured')
        self.assertEqual(len(failure['embedding']['candidates']),35)
        self.assertAlmostEqual(failure['embedding']['top_similarity'],1)

    def test_batch_arrival_survives_first_event_strategy_error(self):
        session=self.system.agent_session(trigger_strategy=lambda trajectory: 1)
        with self.assertRaises(TypeError):session.handle_messages(['one','two','three'])
        self.assertEqual(len(self.logs('trace_received')),3)
        self.assertEqual(len(self.logs('trace_not_processed')),2)
        self.assertEqual(self.logs('trace_failed')[0]['stage'],'trigger')
        self.assertEqual(self.provider.calls,[])

    def test_bridge_setup_error_has_ingress_before_provider_creation(self):
        config={k:str(v) if isinstance(v,Path) else v for k,v in self.config.items()}
        path=Path(self.config['data_dir']).parent/'config.json'
        path.write_text(json.dumps(config),encoding='utf8')
        with patch('dsh_bridge._embedding',side_effect=ValueError('bad endpoint')):
            with self.assertRaises(ValueError):
                handle({'management_root':str(ROOT),'config_path':str(path),'messages':['hello']})
        self.assertEqual(len(self.logs('bridge_trace_received')),1)
        self.assertEqual(len(self.logs('bridge_failed')),1)

    def test_diagnostic_failure_does_not_change_nontrigger_result(self):
        self.system.embedding=None
        result=self.system.agent_session().handle_raw_trace({'role':'assistant','content':'context'})
        self.assertEqual(result.status,RetrievalStatus.NOT_TRIGGERED)
        complete=self.logs('trace_completed')[0]
        self.assertFalse(complete['triggered'])
        self.assertEqual(complete['embedding']['status'],'failed')

    def test_parallel_json_lines_and_structured_secret_redaction(self):
        def append(i):
            RuntimeAudit(self.config['data_dir']).emit('parallel',sequence=i,
                raw={'api_key':'do-not-log','nested':{'authorization':'hidden'}})
        with ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(append,range(30)))
        rows=self.logs('parallel')
        self.assertEqual(sorted(r['sequence'] for r in rows),list(range(30)))
        self.assertNotIn('do-not-log',self.system.audit.path.read_text())
        self.assertEqual(rows[0]['raw']['nested']['authorization'],'[REDACTED]')

    def test_invalid_numeric_parameter_is_still_audited(self):
        with self.assertRaises(ValueError):self.system.retrieve('q',min_similarity=float('nan'))
        self.assertEqual(len(self.logs('retrieval_failed')),1)
