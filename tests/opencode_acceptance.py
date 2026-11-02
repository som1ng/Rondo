"""Opt-in offline npm -> project discovery -> OpenCode V2 checks with a loopback model fixture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urlencode, urlsplit

from codex_acceptance import emit_summary, run
from mcp_hosts import JsonProcess, NO_WINDOW, clean_environment, make_cases, native_executable
from mcp_model_fixture import HostCheckError, ModelFixture, decode_content, verify_result


class OpenCodeModel(ModelFixture):
    def __init__(self, cases=(), *, present=True):
        super().__init__('opencode', cases, tools_present=present)

    def verify_tools(self, tools):
        if tools is None:
            tools = []
        if not isinstance(tools, list) or any(not isinstance(row, dict)
                or not isinstance(row.get('function', row), dict) for row in tools):
            raise HostCheckError('invalid OpenCode tool catalog')
        # 2.2.5 advertises its built-in skill loader even with no enabled skills.
        # Accept only this observed built-in; every MCP tool still passes the strict catalog check.
        own = [row for row in tools if row.get('function', row).get('name') != 'skill']
        if len(tools) - len(own) > 1:
            raise HostCheckError('duplicate built-in skill tool')
        super().verify_tools(own)

    def accept(self, call_id, content):
        value = decode_content(content)
        # V2 wraps isError tool results; the original adapter JSON remains in the message.
        if set(value) == {'error', 'content'}:
            error = value['error']
            if (value['content'] != [] or not isinstance(error, dict)
                    or set(error) != {'type', 'message'} or error['type'] != 'tool.execution'):
                raise HostCheckError('unexpected OpenCode tool error wrapper')
            value = decode_content(error['message'])
            verify_result(value, {'label': 'policy_error'})
            content = json.dumps(value)
        super().accept(call_id, content)

    def verify_complete(self):
        super().verify_complete()
        if self.requests != len(self.cases) + 1:
            raise HostCheckError('OpenCode exceeded the deterministic model request count')


def isolated_environment(state, fixture):
    config = {
        '$schema': 'https://opencode.ai/config.json', 'model': 'fixture/fixture',
        'update': 'disable', 'snapshots': False, 'compaction': {'auto': False},
        'agents': {'title': {'disabled': True}},
        'providers': {'fixture': {
            'name': 'Local fixture', 'package': '@opencode/ai/providers/openai-compatible',
            'settings': {'baseURL': fixture.url + '/v1', 'apiKey': 'fixture-not-a-real-key'},
            'models': {'fixture': {'name': 'Fixture', 'capabilities': {'tools': True},
                                   'limit': {'context': 128000, 'output': 8192}}}}},
        'permissions': [{'action': '*', 'resource': '*', 'effect': 'deny'},
                        {'action': 'dll_doctor_*', 'resource': '*', 'effect': 'allow'}],
        'policies': [{'action': 'provider.use', 'resource': '*', 'effect': 'deny'},
                     {'action': 'provider.use', 'resource': 'fixture', 'effect': 'allow'},
                     {'action': 'plugin.use', 'resource': '*', 'effect': 'deny'},
                     {'action': 'skill.use', 'resource': '*', 'effect': 'deny'}],
    }
    env = clean_environment()
    home = state / 'home'
    env.update(USERPROFILE=str(home), HOME=str(home), HOMEDRIVE=home.drive,
        HOMEPATH=str(home)[len(home.drive):], APPDATA=str(home / 'AppData/Roaming'),
        LOCALAPPDATA=str(home / 'AppData/Local'), PROGRAMDATA=str(state / 'programdata'),
        OPENCODE_CONFIG_DIR=str(state / 'config/opencode'), OPENCODE_CONFIG_CONTENT=json.dumps(config),
        OPENCODE_DB=str(state / 'opencode.sqlite'), OPENCODE_DISABLE_AUTOUPDATE='true',
        OPENCODE_PASSWORD=secrets.token_urlsafe(24),
        OPENCODE_DISABLE_MODELS_FETCH='true', OPENCODE_DISABLE_DEFAULT_PLUGINS='true',
        XDG_CONFIG_HOME=str(state / 'config'), XDG_DATA_HOME=str(state / 'data'),
        XDG_CACHE_HOME=str(state / 'cache'), XDG_STATE_HOME=str(state / 'state'))
    return env


def command(exe, server_url):
    # No MCP override or explicit config file: the client must discover the project.
    return [exe, 'run', '--server', server_url, '--format', 'json', '--model', 'fixture/fixture',
            '--title', 'Rondo local acceptance', 'Run the local MCP integration fixture.']


def check_ancestors(project):
    # V2 reads ancestors above the Git root too; do not let an ambient MCP or plugin enter this test.
    for directory in project.parents:
        for relative in ('opencode.json', 'opencode.jsonc', '.opencode/opencode.json', '.opencode/opencode.jsonc'):
            if (directory / relative).exists():
                raise HostCheckError('ancestor OpenCode configuration would contaminate project discovery')


def mcp_ready(response, present):
    rows = response.get('data') if isinstance(response, dict) else None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise HostCheckError('invalid OpenCode MCP status')
    if not rows:
        return not present
    if not present or len(rows) != 1 or rows[0].get('name') != 'dll_doctor':
        raise HostCheckError('unexpected server in isolated OpenCode MCP status')
    state = rows[0].get('status')
    status = state.get('status') if isinstance(state, dict) else None
    if status == 'connected':
        return True
    if status not in ('pending', 'connecting'):
        raise HostCheckError('OpenCode did not connect to the installed MCP server')
    return False


def wait_for_mcp(exe, url, project, env, present, deadline):
    target = '/api/mcp?' + urlencode({'location[directory]': str(project)})
    while (remaining := deadline - time.monotonic()) > 0:
        response = subprocess.run([exe, 'api', 'get', target, '--server', url], cwd=project, env=env,
            stdin=subprocess.DEVNULL, capture_output=True, timeout=min(10, remaining), creationflags=NO_WINDOW)
        if response.returncode or len(response.stdout) > 1024 * 1024:
            raise HostCheckError('OpenCode MCP readiness query failed')
        if mcp_ready(json.loads(response.stdout), present):
            return
    raise HostCheckError('OpenCode MCP connection deadline exceeded')


def execute(exe, project, state, fixture, timeout):
    state.mkdir()
    for directory in ('home', 'programdata'):
        (state / directory).mkdir()
    env = isolated_environment(state, fixture)
    deadline = time.monotonic() + timeout
    # A fresh 2.2.5 service can report no MCPs while its initial connections are pending.
    # Keep our private server alive and wait for actual readiness before the model turn.
    host = JsonProcess([exe, 'serve', '--stdio', '--hostname', '127.0.0.1', '--port', '0'], project, timeout, env)
    try:
        url = host.wait(lambda event: 'url' in event)['url']
        address = urlsplit(url)
        if (address.scheme != 'http' or address.hostname != '127.0.0.1' or not address.port
                or address.username or address.password or address.path not in ('', '/') or address.query or address.fragment):
            raise HostCheckError('OpenCode private server did not bind the expected loopback address')
        wait_for_mcp(exe, url, project, env, fixture.tools_present, deadline)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise HostCheckError('OpenCode acceptance deadline exceeded before the model turn')
        proc = JsonProcess(command(exe, url), project, remaining, env)
        events = []
        try:
            proc.process.stdin.close()
            proc.wait(lambda event: events.append(event) or False, allow_eof=True)
            proc.process.wait(timeout=5)
            if proc.process.returncode:
                raise HostCheckError('OpenCode exited unsuccessfully during local acceptance')
        finally:
            proc.close()
    finally:
        host.close()
    verify_events(events)
    return events


def verify_events(events):
    finishes = [event.get('part') for event in events if event.get('type') == 'step_finish']
    if (not finishes or any(not isinstance(part, dict) for part in finishes)
            or finishes[-1].get('reason') != 'stop'
            or sum(part.get('reason') == 'stop' for part in finishes) != 1
            or any(event.get('type') == 'error' for event in events)):
        raise HostCheckError('OpenCode did not complete a successful fixture turn')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path, help='trusted local Rondo npm .tgz; no registry download')
    parser.add_argument('--opencode', required=True, help='installed native OpenCode .exe, tested with 2.2.5')
    parser.add_argument('--dll', required=True, type=Path, help='repository-built inert noop_fixture.dll (never loaded)')
    parser.add_argument('--timeout', type=int, default=120, help='per OpenCode run deadline, seconds (30-300)')
    parser.add_argument('--output', type=Path, help='new sanitized summary file; refuses overwrite')
    args = parser.parse_args()
    if os.name != 'nt' or not 30 <= args.timeout <= 300:
        parser.error('requires Windows and a timeout of 30-300 seconds')
    if args.output and args.output.exists():
        parser.error('output already exists; choose a new file')
    if args.output and not args.output.resolve().parent.is_dir():
        parser.error('output directory does not exist')
    stage = 'inputs'
    summary = {'status': 'failed', 'client': 'opencode', 'external_model_calls': 0,
               'model_behavior_evaluation': 'not_run', 'model_requests': 0, 'checks': []}
    try:
        exe = native_executable(args.opencode)
        archive, dll = args.archive.resolve(strict=True), args.dll.resolve(strict=True)
        npm = shutil.which('npm.cmd')
        if not npm:
            raise HostCheckError('npm.cmd is required')
        summary['archive_sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
        version = run([exe, '--version'], archive.parent).strip()
        if version != 'opencode v2.2.5':
            raise HostCheckError('this acceptance driver requires OpenCode 2.2.5')
        summary['client_version'] = version
        with tempfile.TemporaryDirectory(prefix='rondo-opencode-acceptance-') as tmp:
            base = Path(tmp).resolve()
            prefix, project = base / '中文 global', base / '项目 space 🚀'
            project.mkdir()
            check_ancestors(project)
            run(['git', 'init', '-q', project], base)
            marker = project / 'keep.txt'
            marker.write_text('unrelated project file', encoding='utf-8')
            stage = 'offline npm install'
            npm_args = [npm, '--prefix', prefix, '--cache', base / 'empty-cache', '--offline',
                        '--registry=http://127.0.0.1:9', '--ignore-scripts', '--no-audit', '--no-fund']
            run([*npm_args, 'install', '-g', archive], base)
            shim = prefix / 'rondo.cmd'
            package = prefix / 'node_modules/@som1ng/rondo'
            stage = 'self-check'
            check = json.loads(run([shim, 'self-check', '--json'], project))
            if (check['status'] != 'success' or check['runtime_verification'] != 'passed'
                    or len(check['checks']) != 8 or any(row['status'] != 'passed' for row in check['checks'])):
                raise HostCheckError('installed package self-check failed')
            summary['package_version'] = check['package_version']
            summary['checks'] += ['offline_npm_install', 'self_check_8']
            cli = package / 'runtime' / check['architecture'] / 'rondo.exe'
            cases = make_cases(str(cli), dll, project, args.timeout)

            def discovery(label, present, tool_cases=()):
                nonlocal stage
                stage = label
                with OpenCodeModel(tool_cases, present=present) as fixture:
                    try:
                        execute(exe, project, base / ('state-' + label), fixture, args.timeout)
                        fixture.verify_complete()
                    except HostCheckError:
                        if fixture.failure:
                            raise HostCheckError(fixture.failure) from None
                        raise
                    finally:
                        summary['model_requests'] += fixture.requests
                summary['checks'].append(label)

            discovery('absent_config', False)
            stage = 'project setup'
            installer = [shim, 'setup', '--integration', 'mcp', '--agent', 'opencode', '--scope', 'project',
                         '--project', project, '--client', exe, '--allow-root', project, '--verify']
            installed = json.loads(run(installer, project))
            if installed['action'] != 'installed':
                raise HostCheckError('MCP setup failed')
            config_path, receipt_path = project / 'opencode.json', project / '.dll-doctor/mcp-opencode.json'
            config_before = config_path.read_bytes()
            config = json.loads(config_before)
            entry = config['mcp']['servers']['dll_doctor']
            if entry.get('disabled') is not False or entry.get('codemode') is not False or 'enabled' in entry:
                raise HostCheckError('installer did not generate a directly exposed native V2 entry')
            receipt = json.loads(receipt_path.read_bytes())
            if (Path(receipt['runtime']['cli']['path']) != cli
                    or not Path(receipt['runtime']['server']['path']).is_relative_to(package)
                    or receipt['runtime']['client']['version'] != '2.2.5'):
                raise HostCheckError('project installation did not bind the installed npm runtime')
            summary['checks'].append('native_v2_project_setup')
            discovery('project_seven_tools_and_four_calls', True, cases)
            summary['tool_checks'] = [case['label'] for case in cases]
            stage = 'repeat and verify'
            if json.loads(run(installer, project))['action'] != 'unchanged':
                raise HostCheckError('repeated MCP setup changed the installation')
            query = ['--integration', 'mcp', '--agent', 'opencode', '--scope', 'project', '--project', project]
            if json.loads(run([shim, 'verify', *query], project))['action'] != 'verified':
                raise HostCheckError('MCP verification failed')
            summary['checks'].append('repeat_setup_and_verify')
            stage = 'uninstall'
            if config_path.read_bytes() != config_before:
                raise HostCheckError('client changed the managed project configuration')
            if json.loads(run([shim, 'uninstall', *query], project))['action'] != 'removed':
                raise HostCheckError('MCP uninstall failed')
            if config_path.exists() or receipt_path.exists():
                raise HostCheckError('MCP uninstall left managed configuration behind')
            discovery('uninstalled_config', False)
            stage = 'npm uninstall'
            run([*npm_args, 'uninstall', '-g', '@som1ng/rondo'], base)
            if shim.exists() or package.exists() or marker.read_text(encoding='utf-8') != 'unrelated project file':
                raise HostCheckError('npm uninstall left package files or changed an unrelated file')
            summary['checks'].append('npm_uninstall')
        summary['status'] = 'passed'
    except (HostCheckError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        summary.update(stage=stage, message=str(error) if isinstance(error, HostCheckError)
                       else 'Acceptance failed at the recorded stage; no success is inferred for later checks.')
    return emit_summary(summary, args.output)


if __name__ == '__main__':
    raise SystemExit(main())
