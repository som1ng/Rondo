"""Offline guards for OpenCode V2 discovery, readiness and returned tool evidence."""
import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mcp_hosts_tests import catalog, cases, envelope
from mcp_model_fixture import HostCheckError, ModelFixture
from opencode_acceptance import (OpenCodeModel, check_ancestors, command, execute,
    isolated_environment, main, mcp_ready, verify_events, wait_for_mcp)


SKILL = {'type': 'function', 'function': {'name': 'skill', 'parameters': {'type': 'object'}}}
POLICY = {'source': 'adapter', 'cli_exit_code': None, 'report': None,
          'error': {'code': 'PATH_POLICY', 'message': 'Use an absolute local drive path.'}}


def wrapped(value):
    return {'error': {'type': 'tool.execution', 'message': json.dumps(value)}, 'content': []}


def status(value, name='dll_doctor'):
    return {'data': [{'name': name, 'status': {'status': value}}]}


def events():
    return [{'type': 'step_start'}, {'type': 'step_finish', 'part': {'reason': 'tool-calls'}},
            {'type': 'step_start'}, {'type': 'text', 'part': {'text': 'Local fixture complete.'}},
            {'type': 'step_finish', 'part': {'reason': 'stop'}}]


class OpenCodeAcceptanceTests(unittest.TestCase):
    def fixture(self, *args, **kwargs):
        fixture = OpenCodeModel(*args, **kwargs)
        self.addCleanup(fixture.server.server_close)
        return fixture

    def test_exact_catalog_allows_only_the_observed_builtin(self):
        fixture = self.fixture()
        fixture.verify_tools(catalog('opencode'))
        fixture.verify_tools([SKILL, *catalog('opencode')])
        invalid = [None, {}, [None], [{'function': None}], [], catalog('opencode')[:-1],
            catalog('opencode') * 2, [SKILL, SKILL, *catalog('opencode')],
            [{'name': 'shell'}, *catalog('opencode')], [{'name': 'other_server_tool'}, *catalog('opencode')]]
        for rows in invalid:
            with self.subTest(rows=rows), self.assertRaises(HostCheckError):
                fixture.verify_tools(rows)

    def test_schema_bounds_survive_builtin_filtering(self):
        rows = [copy.deepcopy(SKILL), *catalog('opencode')]
        rows[1]['function']['parameters']['properties']['timeout_ms']['maximum'] = 30001
        with self.assertRaises(HostCheckError):
            self.fixture().verify_tools(rows)

    def test_absent_config_cannot_advertise_any_mcp(self):
        fixture = self.fixture(present=False)
        for rows in (None, [], [SKILL]):
            fixture.verify_tools(rows)
        for rows in (catalog('opencode'), [SKILL, {'name': 'other_tool'}], [SKILL, SKILL]):
            with self.subTest(rows=rows), self.assertRaises(HostCheckError):
                fixture.verify_tools(rows)
        strict = ModelFixture('opencode', [], tools_present=False)
        self.addCleanup(strict.server.server_close)
        with self.assertRaises(HostCheckError):
            strict.verify_tools([SKILL])

    def test_completion_requires_returned_evidence_and_exact_request_count(self):
        fixture = self.fixture([*cases(), {'label': 'policy_error', 'tool': 'inspect_pe',
            'arguments': {'path': 'relative.dll'}}])
        body = {'stream': True, 'model': 'fixture', 'tools': [SKILL, *catalog('opencode')], 'messages': []}
        self.assertIn('dll_doctor_read_report', fixture.respond('/v1/chat/completions', body))
        with self.assertRaises(HostCheckError):
            fixture.verify_complete()
        body['messages'].append({'role': 'tool', 'tool_call_id': 'fixture_0', 'content': json.dumps(envelope())})
        self.assertIn('dll_doctor_inspect_pe', fixture.respond('/v1/chat/completions', body))
        body['messages'].append({'role': 'tool', 'tool_call_id': 'fixture_1', 'content': json.dumps(wrapped(POLICY))})
        self.assertIn('Local fixture complete.', fixture.respond('/v1/chat/completions', body))
        fixture.verify_complete()
        self.assertEqual(fixture.results[1], POLICY)
        fixture.respond('/v1/chat/completions', body)
        with self.assertRaises(HostCheckError):
            fixture.verify_complete()

    def test_error_wrapper_does_not_weaken_evidence_or_order_checks(self):
        fixture = self.fixture([{'label': 'policy_error'}])
        with self.assertRaises(HostCheckError):
            fixture.accept('fixture_0', json.dumps(wrapped(POLICY)))
        fixture.issued.add(0)
        invalid = [wrapped(dict(POLICY, error={'code': 'INTERNAL', 'message': 'not a path failure'})),
            wrapped(envelope()), dict(wrapped(POLICY), content=[{'type': 'text', 'text': 'extra'}]),
            {'error': {'type': 'other', 'message': json.dumps(POLICY)}, 'content': []},
            {'error': {'type': 'tool.execution', 'message': 'not JSON'}, 'content': []},
            {'error': None, 'content': []}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(HostCheckError):
                fixture.accept('fixture_0', json.dumps(value))
        fixture.accept('fixture_0', json.dumps(wrapped(POLICY)))
        successful = self.fixture(cases())
        successful.issued.add(0)
        with self.assertRaises(HostCheckError):
            successful.accept('fixture_0', json.dumps(wrapped(POLICY)))
        changed = envelope()
        changed['report']['duration_ms'] += 1
        with self.assertRaises(HostCheckError):
            successful.accept('fixture_0', json.dumps(changed))

    def test_readiness_distinguishes_cold_start_from_connected_and_failed(self):
        self.assertFalse(mcp_ready({'data': []}, True))
        self.assertTrue(mcp_ready({'data': []}, False))
        self.assertFalse(mcp_ready(status('pending'), True))
        self.assertFalse(mcp_ready(status('connecting'), True))
        self.assertTrue(mcp_ready(status('connected'), True))
        for response, present in [(status('connected'), False), (status('failed'), True),
                (status('disabled'), True), (status('connected', 'other'), True),
                ({'data': status('connected')['data'] * 2}, True), ({'data': [None]}, True),
                ({'data': [{'name': 'dll_doctor', 'status': None}]}, True), ({}, True), ([], True)]:
            with self.subTest(response=response), self.assertRaises(HostCheckError):
                mcp_ready(response, present)

    def test_readiness_waits_on_the_same_server_without_config_injection(self):
        responses = [subprocess.CompletedProcess([], 0, json.dumps(value).encode())
                     for value in ({'data': []}, status('pending'), status('connected'))]
        with patch('opencode_acceptance.time.monotonic', return_value=1), \
                patch('opencode_acceptance.subprocess.run', side_effect=responses) as invoke:
            wait_for_mcp('opencode.exe', 'http://127.0.0.1:12345', Path.cwd(), {}, True, 30)
        self.assertEqual(invoke.call_count, 3)
        for call in invoke.call_args_list:
            argv = call.args[0]
            self.assertEqual(argv[1:3], ['api', 'get'])
            self.assertTrue(argv[3].startswith('/api/mcp?location%5Bdirectory%5D='))
            self.assertEqual(argv[4:], ['--server', 'http://127.0.0.1:12345'])
        with patch('opencode_acceptance.time.monotonic', return_value=30), \
                patch('opencode_acceptance.subprocess.run') as invoke, self.assertRaises(HostCheckError):
            wait_for_mcp('opencode.exe', 'http://127.0.0.1:12345', Path.cwd(), {}, True, 30)
        invoke.assert_not_called()

    def test_missing_failed_or_nonterminal_completion_is_rejected(self):
        verify_events(events())
        for stream in ([], events()[:-1], [*events(), events()[-1]],
                [*events(), {'type': 'error'}], [*events(), {'type': 'step_finish', 'part': {'reason': 'length'}}],
                [{'type': 'step_finish', 'part': None}]):
            with self.subTest(stream=stream), self.assertRaises(HostCheckError):
                verify_events(stream)

    def test_environment_isolated_without_disabling_project_discovery(self):
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw).resolve()
            fixture = SimpleNamespace(url='http://127.0.0.1:12345')
            ambient = {key: 'do-not-copy' for key in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'NODE_OPTIONS',
                'OPENCODE_CONFIG', 'OPENCODE_CONFIG_DIR', 'OPENCODE_CONFIG_CONTENT', 'OPENCODE_PASSWORD',
                'OPENCODE_DISABLE_PROJECT_CONFIG', 'HTTP_PROXY')}
            with patch.dict(os.environ, ambient):
                env = isolated_environment(state, fixture)
            self.assertNotIn('do-not-copy', json.dumps(env))
            self.assertNotIn('OPENCODE_CONFIG', env)
            self.assertNotIn('OPENCODE_DISABLE_PROJECT_CONFIG', env)
            config = json.loads(env['OPENCODE_CONFIG_CONTENT'])
            self.assertNotIn('mcp', config)
            self.assertEqual(config['providers']['fixture']['settings']['baseURL'], fixture.url + '/v1')
            for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA', 'OPENCODE_CONFIG_DIR',
                        'OPENCODE_DB', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME'):
                self.assertTrue(Path(env[key]).is_relative_to(state), key)
            argv = command('opencode.exe', 'http://127.0.0.1:12345')
            self.assertEqual(argv[2:4], ['--server', 'http://127.0.0.1:12345'])
            self.assertFalse(any('mcp' in arg.lower() for arg in argv[:-1]))
            self.assertNotIn('--pure', argv)

    def test_private_server_is_closed_if_readiness_fails(self):
        with tempfile.TemporaryDirectory() as raw, patch('opencode_acceptance.JsonProcess') as process:
            process.return_value.wait.return_value = {'url': 'http://127.0.0.1:12345'}
            with patch('opencode_acceptance.wait_for_mcp', side_effect=HostCheckError('not connected')), \
                    self.assertRaises(HostCheckError):
                execute('opencode.exe', Path(raw), Path(raw) / 'state', self.fixture(), 30)
            self.assertEqual(process.call_count, 1)
            process.return_value.close.assert_called_once()

    def test_private_server_cannot_redirect_the_client_off_loopback(self):
        with tempfile.TemporaryDirectory() as raw, patch('opencode_acceptance.JsonProcess') as process, \
                patch('opencode_acceptance.wait_for_mcp') as readiness:
            process.return_value.wait.return_value = {'url': 'https://example.invalid'}
            with self.assertRaises(HostCheckError):
                execute('opencode.exe', Path(raw), Path(raw) / 'state', self.fixture(), 30)
            readiness.assert_not_called()
            self.assertEqual(process.call_count, 1)
            process.return_value.close.assert_called_once()

    def test_ancestor_configs_are_rejected_but_project_config_is_discovered(self):
        with tempfile.TemporaryDirectory() as raw:
            parent = Path(raw).resolve()
            project = parent / 'project'
            project.mkdir()
            (project / 'opencode.json').write_text('{}', encoding='utf-8')
            check_ancestors(project)
            for relative in ('opencode.json', 'opencode.jsonc', '.opencode/opencode.json', '.opencode/opencode.jsonc'):
                file = parent / relative
                file.parent.mkdir(exist_ok=True)
                file.write_text('{}', encoding='utf-8')
                with self.subTest(relative=relative), self.assertRaises(HostCheckError):
                    check_ancestors(project)
                file.unlink()

    def test_output_preflight_prevents_client_execution(self):
        with tempfile.TemporaryDirectory() as raw:
            existing = Path(raw) / 'existing.json'
            existing.write_text('keep', encoding='utf-8')
            for output in (existing, Path(raw) / 'missing/out.json'):
                argv = ['opencode_acceptance.py', '--archive', 'archive.tgz', '--opencode', 'opencode.exe',
                        '--dll', 'fixture.dll', '--output', str(output)]
                with patch('sys.argv', argv), patch('opencode_acceptance.native_executable') as native, \
                        redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    main()
                self.assertEqual(error.exception.code, 2)
                native.assert_not_called()
            self.assertEqual(existing.read_text(encoding='utf-8'), 'keep')

    def test_failed_summary_withholds_private_exception_and_records_no_success(self):
        argv = ['opencode_acceptance.py', '--archive', 'archive.tgz', '--opencode', 'opencode.exe', '--dll', 'fixture.dll']
        stdout = io.StringIO()
        with patch('sys.argv', argv), redirect_stdout(stdout), \
                patch('opencode_acceptance.native_executable', side_effect=OSError('private-path-and-token')):
            self.assertEqual(main(), 1)
        summary = json.loads(stdout.getvalue())
        self.assertEqual(summary['status'], 'failed')
        self.assertEqual(summary['checks'], [])
        self.assertEqual(summary['model_requests'], 0)
        self.assertNotIn('private-path-and-token', stdout.getvalue())


if __name__ == '__main__':
    unittest.main()
