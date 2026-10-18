import tempfile
import unittest
from pathlib import Path

import error_clustering_experiment as experiment
import strategy_clustering as canonical


class CanonicalEntryPointTests(unittest.TestCase):
    def test_canonical_entry_point_reuses_strategy_pipeline(self):
        self.assertIs(canonical.run, experiment.run)
        self.assertIs(canonical.scan, experiment.scan)
        self.assertIs(canonical.group, experiment.group)
        self.assertIs(canonical.STRATEGY_REGISTRY, experiment.STRATEGY_REGISTRY)

    def test_canonical_cli_lists_all_registered_strategies(self):
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, str(Path(canonical.__file__)), '--list-strategies'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('native-code', 'stack-site', 'test-case', 'config-change', 'dependency-change'):
            self.assertIn(name + ':', result.stdout)


class ErrorGroupingTests(unittest.TestCase):
    def test_codes_do_not_collide_and_preserve_sqlstate(self):
        result = experiment.detect('error TS2322: mismatch\nerror CS2322: mismatch\nSQLSTATE[23505]', 'tool_result')
        keys = {r['error_key'] for r in result if r['strategy'] == 'native-code'}
        self.assertEqual(keys, {'typescript:TS2322', 'csharp:CS2322', 'sqlstate:23505'})

    def test_source_code_and_success_are_not_failures(self):
        self.assertEqual(experiment.detect('```python\nclass SomeError(Exception):\n    pass\n```\n0 errors, 0 failures', 'assistant_text'), [])
        self.assertEqual(experiment.detect('class SomeError(Exception):', 'tool_result'), [])

    def test_prose_mentions_are_not_observed_outputs(self):
        mentions = experiment.detect('TypeError: incompatible arguments', 'assistant_text')
        observed = experiment.detect('TypeError: incompatible arguments', 'tool_result')
        self.assertTrue(all(e['evidence_kind'] == 'reported_in_text' for e in mentions))
        self.assertTrue(all(e['evidence_kind'] == 'tool_output' for e in observed))

    def test_constants_and_passing_negative_tests_not_errors(self):
        source = '127\tif (ENTER) {\n#define ESYS_BADARG -2\ncode: 0\nPASS [negative]: TypeError: expected\n## DOMException and LexError modules'
        self.assertEqual(experiment.detect(source, 'tool_result'), [])
        self.assertTrue(any(e['error_key'] == 'symbolic-code:ECONNRESET' for e in experiment.detect("code: 'ECONNRESET'", 'tool_result')))

    def test_signed_and_hex_status_agree(self):
        a = experiment.detect('Exit code `-1073741571` = stack overflow', 'assistant_text')
        b = experiment.detect('Exit code 0xC00000FD', 'assistant_text')
        self.assertEqual([r['error_key'] for r in a if r['strategy'] == 'native-code'], [r['error_key'] for r in b if r['strategy'] == 'native-code'])

    def test_opencode_reader(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 's.json'
            path.write_text(json.dumps({'messages': [{'info': {'role': 'assistant'}, 'parts': [{'type': 'tool', 'tool': 'bash', 'state': {'input': {'command': 'test'}, 'output': 'TypeError: bad'}}]}]}), encoding='utf-8')
            events = experiment.raw_events(path)
            self.assertEqual([e['channel'] for e in events], ['tool_call:bash', 'tool_result'])
            self.assertEqual(events[1]['text'], 'TypeError: bad')

    def test_template_drops_locations_but_preserves_unquoted_types(self):
        a = experiment.normalize_message('C:\\one\\x.cpp:12:8: error: expected int, received str')
        b = experiment.normalize_message('D:\\two\\y.cpp:35:4: error: expected int, received str')
        self.assertEqual(a, b)
        self.assertNotEqual(a, experiment.normalize_message('D:\\two\\y.cpp:35:4: error: expected int, received bool'))

    def test_overlapping_memberships_and_residual(self):
        units = [{'unit_id': 'a'}, {'unit_id': 'b'}, {'unit_id': 'empty'}]
        occurrences = []
        for uid, text in [('a', 'TS2322 CS1001'), ('b', 'TS2322')]:
            for entry in experiment.detect(text, 'assistant_text'):
                occurrences.append(entry | {'unit_id': uid, 'session_id': uid, 'source_paths': ['/input.json']})
        groups, residual, summary = experiment.group(units, occurrences, 'native-code')
        self.assertEqual(residual, ['empty'])
        self.assertEqual(summary['group_count'], 2)
        self.assertEqual(sum('a' in g['member_ids'] for g in groups), 2)
        self.assertEqual((groups, residual, summary), experiment.group(units, occurrences, 'native-code'))

    def test_missing_results_not_invented_and_calls_not_scanned(self):
        events = [experiment.project(e, Path('/input.json'), i, i) for i, e in enumerate([
            {'category': 'tool_result'},
            {'category': 'tool_call:Write', 'arguments': {'content': 'TypeError: fake'}, 'text': 'TypeError: fake'},
            {'category': 'assistant_text', 'text': 'Everything completed.'}])]
        result, diagnostic = experiment.scan([{'unit_id': 'a', 'session_id': 's', 'source_paths': [], 'events': events}])
        self.assertEqual(result, [])
        self.assertEqual(diagnostic['tool_result_without_payload'], 1)

    def test_original_result_reader(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 's.jsonl'
            path.write_text('{"message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"a","content":"TypeError: bad"}]}}\n', encoding='utf-8')
            events = experiment.raw_events(path)
            self.assertEqual(events[0]['channel'], 'tool_result')
            self.assertEqual(events[0]['text'], 'TypeError: bad')


class FourAnchorStrategyTests(unittest.TestCase):
    def unit(self, source, cwd='C:/project'):
        events = []
        for i, event in enumerate(source):
            events.append(experiment.project(event | {'cwd': cwd}, Path('/input.json'), i, i))
        return {'unit_id': 'a', 'session_id': 's', 'source_paths': ['/input.json'], 'events': events}

    def test_failures_and_written_test_names_but_not_suite_pass(self):
        u = self.unit([
            {'category': 'tool_result', 'tool_name': 'Bash', 'text': 'PASS T1/ok\nFAIL T1/repeated_destroy: bad\nFAIL tests/test_x.cpp:32 bad'},
            {'category': 'tool_call:Write', 'tool_name': 'Write', 'arguments': {'file_path': 'C:/project/tests/test_life.cpp', 'content': 'TEST("destroy twice") { }'}}])
        hits = list(experiment.strategy_test_case(u))
        self.assertEqual({h['test_name'] for h in hits}, {'T1/repeated_destroy', 'destroy twice'})

    def test_same_test_name_other_project_not_merged(self):
        event = {'category': 'tool_result', 'text': 'FAILED tests/test_x.py::test_same - failed'}
        a = list(experiment.strategy_test_case(self.unit([event], 'C:/one')))
        b = list(experiment.strategy_test_case(self.unit([event], 'C:/two')))
        self.assertNotEqual(a[0]['group_key'], b[0]['group_key'])

    def test_absolute_file_identity_survives_cwd_change(self):
        a = self.unit([{'category': 'assistant_text'}], 'C:/project')
        b = self.unit([{'category': 'assistant_text'}], 'C:/project/tests')
        self.assertEqual(experiment._file_identity(a, 0, 'C:/project/tests/test_x.py'),
                         experiment._file_identity(b, 0, 'C:/project/tests/test_x.py'))
        self.assertEqual(experiment._file_identity(a, 0, 'tests/test_x.py'),
                         experiment._file_identity(b, 0, 'test_x.py'))

    def test_stack_site_python_and_java_direction(self):
        python = 'Traceback (most recent call last):\n  File "C:/project/main.py", line 1, in outer\n  File "C:/project/parser.py", line 9, in parse\nTypeError: bad'
        java = 'java.lang.IllegalArgumentException: bad\n at lib.Parser.parse(Parser.java:9)\n at app.Main.run(Main.java:1)'
        a = list(experiment.strategy_stack_site(self.unit([{'category': 'tool_result', 'text': python}])))
        b = list(experiment.strategy_stack_site(self.unit([{'category': 'tool_result', 'text': java}])))
        self.assertEqual(a[0]['throw_site']['function'], 'parse')
        self.assertEqual(b[0]['throw_site']['function'], 'lib.Parser.parse')

    def test_expected_exception_and_read_source_not_runtime_stack(self):
        text = 'TypeError: expected\n at lib.Test.run(Test.java:2)\nResults: 10 passed, 0 failed'
        self.assertEqual(list(experiment.strategy_stack_site(self.unit([{'category': 'tool_result', 'text': text}]))), [])
        self.assertEqual(list(experiment.strategy_stack_site(self.unit([{'category': 'tool_result', 'tool_name': 'Read', 'text': text}]))), [])

    def test_config_snapshot_edit_complete_path(self):
        u = self.unit([
            {'category': 'tool_call:Read', 'tool_name': 'Read', 'arguments': {'file_path': 'C:/project/settings.json'}},
            {'category': 'tool_result', 'tool_name': 'Read', 'text': '1\t{"nested":{"timeout":10}}'},
            {'category': 'tool_call:Edit', 'tool_name': 'Edit', 'arguments': {'file_path': 'C:/project/settings.json', 'old_string': '10', 'new_string': '20'}}])
        hits = list(experiment.strategy_config_change(u))
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]['key_path'], ['nested', 'timeout'])
        self.assertEqual((hits[0]['old_value'], hits[0]['new_value']), (10, 20))

    def test_arbitrary_data_and_unknown_config_before_not_classified(self):
        events = [
            {'category': 'tool_call:Write', 'arguments': {'file_path': 'C:/project/settings.json', 'content': '{"x":1}'}},
            {'category': 'tool_call:Write', 'arguments': {'file_path': 'C:/project/data.json', 'content': '{"x":1}'}},
            {'category': 'tool_call:Write', 'arguments': {'file_path': 'C:/project/data.json', 'content': '{"x":2}'}}]
        self.assertEqual(list(experiment.strategy_config_change(self.unit(events))), [])

    def test_dependencies_change_and_unknown_baseline_distinguished(self):
        import json
        u = self.unit([
            {'category': 'tool_call:Write', 'arguments': {'file_path': 'C:/project/package.json', 'content': json.dumps({'dependencies': {'unknown-package': '1'}})}},
            {'category': 'tool_call:Edit', 'arguments': {'file_path': 'C:/project/package.json', 'old_string': '"1"', 'new_string': '"2"'}}])
        hits = list(experiment.strategy_dependency_change(u))
        self.assertEqual(hits[0]['operation'], 'declaration_old_unknown')
        self.assertFalse(hits[0]['old_version_known'])
        self.assertEqual(hits[1]['operation'], 'version_changed')
        self.assertEqual((hits[1]['old_version'], hits[1]['new_version']), ('1', '2'))

    def test_config_jsonc_strings_not_destroyed(self):
        d = experiment._structured('{"url":"https://example.com", "value":",}", /* comment */ "flag":true,}', 'x.json')
        self.assertEqual(d['url'], 'https://example.com')
        self.assertEqual(d['value'], ',}')


class StrategyPipelineTests(unittest.TestCase):
    def register(self, name, function):
        experiment.STRATEGY_REGISTRY[name] = function
        self.addCleanup(experiment.STRATEGY_REGISTRY.pop, name)

    def unit(self, events):
        return {'unit_id': 'a', 'session_id': 's', 'source_paths': ['/input.json'],
                'events': [experiment.project(e, Path('/input.json'), i, i) for i, e in enumerate(events)]}

    def test_selected_strategy_only(self):
        def should_not_run(unit):
            raise AssertionError('An unselected strategy was invoked')
        self.register('unselected-probe', should_not_run)
        unit = self.unit([{'category': 'tool_result', 'text': 'error TS2322: TypeError: bad'}])
        matches, _ = experiment.scan([unit], ['native-code'])
        self.assertEqual({m['strategy'] for m in matches}, {'native-code'})
        self.assertEqual(matches[0]['group_key'], matches[0]['error_key'])

    def test_function_can_read_calls_and_multiple_events(self):
        def probe(unit):
            """Temporary test strategy, not a production config classifier."""
            events = unit['events']
            self.assertEqual(events[0]['arguments']['old_string'], '1')
            self.assertEqual(events[0]['arguments']['new_string'], '2')
            self.assertEqual(events[1]['text'], 'PASS retrieved source')
            return [{'group_key': 'probe:changed-value', 'event_position': 0,
                     'evidence_line': '1 -> 2', 'old_value': '1', 'new_value': '2'}]
        self.register('custom-probe', probe)
        unit = self.unit([
            {'category': 'tool_call:Edit', 'arguments': {'old_string': '1', 'new_string': '2'}},
            {'category': 'tool_result', 'tool_name': 'Read', 'text': 'PASS retrieved source'}])
        matches, _ = experiment.scan([unit], ['custom-probe'])
        groups, residual, _ = experiment.group([unit], matches, 'custom-probe')
        self.assertEqual(groups[0]['group_key'], 'probe:changed-value')
        self.assertNotIn('error_key', groups[0])
        self.assertEqual(matches[0]['old_value'], '1')
        self.assertEqual(matches[0]['source_index'], 0)
        self.assertEqual(residual, [])

    def test_unknown_and_empty_selection_fail_before_work(self):
        with self.assertRaisesRegex(ValueError, 'Unknown strategies'):
            experiment.scan([], ['missing-strategy'])
        with self.assertRaisesRegex(ValueError, 'at least one'):
            experiment.scan([], [])

    def test_invalid_source_position_is_rejected(self):
        self.register('invalid-probe', lambda unit: [{'group_key': 'x', 'event_position': 99, 'evidence_line': 'x'}])
        with self.assertRaisesRegex(ValueError, 'event_position'):
            experiment.scan([self.unit([{'category': 'assistant_text', 'text': 'x'}])], ['invalid-probe'])

    def test_list_cli_needs_no_input_paths(self):
        import subprocess
        import sys
        result = subprocess.run([sys.executable, str(Path(experiment.__file__)), '--list-strategies'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('native-code:', result.stdout)

    def test_small_corpus_and_selected_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            expanded, slices, output = root / 'expanded', root / 'slices', root / 'output'
            expanded.mkdir()
            experiment.save(expanded / 'index.json', {'session_count': 2})
            for sid in ('first', 'second'):
                experiment.save(expanded / f'harness__{sid}__segment-01.json', {
                    'harness': 'harness', 'session_id': sid, 'source_file': f'harness/{sid}.jsonl',
                    'events': [{'kind': 'text', 'role': 'assistant', 'text_type': 'text',
                                'text': 'error TS2322: mismatch', 'source_event_index': 0}]})
                experiment.save(slices / f'harness__{sid}' / 'segment-01.json', {
                    'start_event': 1, 'end_event': 1,
                    'events': [{'category': 'assistant_text', 'text': 'error TS2322: mismatch', 'source_index': 0}]})
            summary = experiment.run(expanded, slices, output, strategies=['native-code'])
            self.assertEqual(summary['sessions-2']['strategies']['native-code']['group_count'], 1)
            self.assertEqual(summary['slices-2']['strategies']['native-code']['covered_count'], 2)
            self.assertFalse((output / 'sessions-2' / 'exception-type').exists())
            self.assertEqual(experiment.read(output / 'manifest.json')['selected_strategies'], ['native-code'])
            self.assertIn('group_key_comparison', summary)
            self.assertIn('error_key_comparison', summary)


if __name__ == '__main__':
    unittest.main()
