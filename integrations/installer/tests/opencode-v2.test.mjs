import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { clientVersion, installMcp } from '../src/mcp.mjs';
import { hash, inspectConfig } from '../src/mcp-config.mjs';

async function fixture(t, scope = 'project') {
  const base = await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(), 'rondo-opencode-v2-')));
  const project = path.join(base, '项目 space 🚀'), home = path.join(base, 'home');
  await fs.mkdir(project); await fs.mkdir(home);
  const cli = path.join(base, 'old.exe'), nextCli = path.join(base, 'new.exe');
  const server = path.join(base, 'index.js'), client = path.join(base, 'opencode.exe');
  for (const file of [cli, nextCli, server, client]) await fs.writeFile(file, 'fixture only: ' + path.basename(file));
  const query = { agent: 'opencode', scope, ...(scope === 'project' ? { project } : {}) };
  const options = { ...query, cli, server, client, allowRoot: [project] };
  const root = scope === 'project' ? project : path.join(home, '.config/opencode');
  await fs.mkdir(root, { recursive: true });
  let version = '2.2.5', probes = 0;
  const context = { home, env: {},
    probeCli: async file => { probes++; return { path: file, tool_version: '2.0.0-dev.9',
      schema_version: '1.6', sha256: hash(await fs.readFile(file)) }; },
    probeClient: async (_agent, file) => { probes++; return { path: file, version }; },
    checkServer: async () => { probes++; },
  };
  t.after(async () => {
    assert.equal(path.dirname(base), await fs.realpath(os.tmpdir()));
    assert.ok(path.basename(base).startsWith('rondo-opencode-v2-'));
    await fs.rm(base, { recursive: true });
  });
  return { base, root, query, options, nextCli, context, probes: () => probes, version: value => { version = value; } };
}

test('client version parsing adds the V2 banner and retains supported V1/Codex/Claude output', () => {
  for (const [agent, version, banners] of [
    ['opencode', '2.2.5', ['opencode v2.2.5', '2.2.5']],
    ['opencode', '1.19.4', ['1.19.4']],
    ['codex', '0.164.0', ['codex-cli 0.164.0', '0.164.0']],
    ['claude', '2.1.310', ['2.1.310 (Claude Code)', '2.1.310']],
  ]) for (const banner of banners) assert.equal(clientVersion(agent, banner), version);
  for (const banner of ['opencode v2.2.4', 'opencode v2.2.5-dev', '2.0.0', 'opencode v2.2.5\nextra']) {
    assert.throws(() => clientVersion('opencode', banner), { code: 'MCP_CLIENT_VERSION' });
  }
});

for (const scope of ['project', 'user']) {
  test(`OpenCode V2/${scope}: native install, repeat, upgrade, verification and complete removal`, async t => {
    const f = await fixture(t, scope);
    const preview = await installMcp('setup', { ...f.options, dryRun: true }, f.context);
    assert.equal(f.probes(), 0);
    assert.equal(preview.executable_probes, 'not_run');
    assert.deepEqual(Object.keys(preview.managed_entries_by_client_version), ['1.19.4', '2.2.5']);
    assert.equal(preview.managed_entries_by_client_version['1.19.4'].enabled, true);
    assert.equal(preview.managed_entries_by_client_version['2.2.5'].codemode, false);
    assert.deepEqual(await fs.readdir(f.root), []);
    const installed = await installMcp('setup', { ...f.options, verify: true }, f.context);
    const original = await fs.readFile(installed.config);
    const config = JSON.parse(original), entry = config.mcp.servers.dll_doctor;
    assert.equal(config.$schema, 'https://opencode.ai/config.json');
    assert.equal(config.mcp.dll_doctor, undefined);
    assert.deepEqual(entry, { type: 'local', command: [process.execPath, f.options.server, '--cli', f.options.cli,
      '--allow-root', f.options.allowRoot[0]], disabled: false, codemode: false });
    assert.equal((await installMcp('setup', f.options, f.context)).action, 'unchanged');
    assert.deepEqual(await fs.readFile(installed.config), original);
    const next = { ...f.options, cli: f.nextCli };
    assert.equal((await installMcp('upgrade', { ...next, dryRun: true }, f.context)).managed_entry.codemode, false);
    assert.equal((await installMcp('upgrade', next, f.context)).action, 'upgraded');
    assert.equal((await installMcp('verify', f.query, f.context)).action, 'verified');
    assert.equal((await installMcp('upgrade', next, f.context)).action, 'unchanged');
    const receipt = JSON.parse(await fs.readFile(installed.receipt));
    assert.equal(receipt.runtime.client.version, '2.2.5');
    assert.ok(receipt.entry.command.includes(f.nextCli));
    await installMcp('uninstall', f.query, f.context);
    for (const file of [installed.config, installed.receipt]) assert.equal(await fs.stat(file).catch(() => null), null);
  });
}

test('V2 JSONC editing preserves MCP defaults, other servers, credentials and later comments', async t => {
  const f = await fixture(t), file = path.join(f.root, 'opencode.jsonc');
  const original = '{\r\n // project note\r\n "model":"keep",\r\n "mcp":{ "timeout":{"catalog":45000},\r\n'
    + ' "servers":{"other":{"type":"remote","url":"https://example.invalid/mcp",'
    + '"headers":{"TOKEN":"private-fixture-never-copy"}}}},\r\n}\r\n';
  await fs.writeFile(file, original);
  const installed = await installMcp('setup', f.options, f.context);
  const changed = (await fs.readFile(file, 'utf8')).replace('// project note', '// later project note');
  await fs.writeFile(file, changed);
  assert.equal((await installMcp('upgrade', { ...f.options, cli: f.nextCli }, f.context)).action, 'upgraded');
  assert.ok(!(await fs.readFile(installed.receipt, 'utf8')).includes('private-fixture-never-copy'));
  await installMcp('uninstall', f.query, f.context);
  const remaining = await fs.readFile(file, 'utf8');
  assert.deepEqual(inspectConfig('opencode', remaining).data, inspectConfig('opencode', original).data);
  assert.ok(remaining.includes('// later project note\r\n'));
});

test('legacy V1 receipts upgrade to V2 in place, including when scope was omitted', async t => {
  const f = await fixture(t);
  f.version('1.19.4');
  const installed = await installMcp('setup', f.options, f.context);
  const record = JSON.parse(await fs.readFile(installed.receipt));
  delete record.scope;
  await fs.writeFile(installed.receipt, JSON.stringify(record));
  const before = await fs.readFile(installed.config);
  f.version('2.2.5');
  await assert.rejects(installMcp('verify', f.query, f.context), { code: 'MCP_RUNTIME_CHANGED' });
  assert.equal((await installMcp('upgrade', f.options, f.context)).action, 'upgraded');
  assert.deepEqual(await fs.readFile(installed.config), before);
  assert.equal((await installMcp('verify', f.query, f.context)).action, 'verified');
  assert.equal(JSON.parse(await fs.readFile(installed.receipt)).runtime.client.version, '2.2.5');
  await installMcp('uninstall', f.query, f.context);
  assert.equal(await fs.stat(installed.config).catch(() => null), null);
});

test('V1 downgrade of native V2 configuration is rejected before any writes', async t => {
  const f = await fixture(t), installed = await installMcp('setup', f.options, f.context);
  const before = await Promise.all([installed.config, installed.receipt].map(file => fs.readFile(file)));
  f.version('1.19.4');
  for (const command of ['setup', 'upgrade']) {
    await assert.rejects(installMcp(command, f.options, f.context), { code: 'MCP_CLIENT_VERSION' });
    assert.deepEqual(await Promise.all([installed.config, installed.receipt].map(file => fs.readFile(file))), before);
  }
  assert.equal(await fs.stat(path.join(f.root, '.dll-doctor/mcp-opencode.lock')).catch(() => null), null);
  await installMcp('uninstall', f.query, f.context);
});

test('unowned, ambiguous and malformed V1/V2 entries are preserved', async t => {
  const f = await fixture(t), file = path.join(f.root, 'opencode.jsonc');
  for (const [mcp, code] of [
    [{ dll_doctor: { type: 'local', command: ['user.exe'], enabled: true } }, 'MCP_CONFLICT'],
    [{ servers: { dll_doctor: { type: 'local', command: ['user.exe'] } } }, 'MCP_CONFLICT'],
    [{ dll_doctor: {}, servers: { dll_doctor: {} } }, 'MCP_CONFIG'],
    [{ servers: [] }, 'MCP_CONFIG'], [{ servers: null }, 'MCP_CONFIG'],
    [{ servers: { type: 'local', command: ['legacy-server.exe'] } }, 'MCP_CONFIG'],
  ]) {
    const source = JSON.stringify({ mcp });
    await fs.writeFile(file, source);
    for (const command of ['setup', 'uninstall']) {
      await assert.rejects(installMcp(command, command === 'setup' ? f.options : f.query, f.context), { code });
      assert.equal(await fs.readFile(file, 'utf8'), source);
    }
  }
  assert.equal(f.probes(), 0);
});

test('moving the managed entry, enabling Code Mode or tampering with V2 receipt versions cannot authorize edits', async t => {
  const f = await fixture(t), installed = await installMcp('setup', f.options, f.context);
  const original = await fs.readFile(installed.config), receipt = await fs.readFile(installed.receipt);
  const moved = JSON.parse(original);
  moved.mcp.dll_doctor = moved.mcp.servers.dll_doctor;
  delete moved.mcp.servers;
  for (const changed of [JSON.stringify(moved), original.toString().replace('"codemode": false', '"codemode": true')]) {
    await fs.writeFile(installed.config, changed);
    for (const command of ['verify', 'uninstall', 'upgrade']) {
      await assert.rejects(installMcp(command, command === 'upgrade' ? f.options : f.query, f.context), { code: 'MCP_CONFIG' });
      assert.equal(await fs.readFile(installed.config, 'utf8'), changed);
      assert.deepEqual(await fs.readFile(installed.receipt), receipt);
    }
  }
  await fs.writeFile(installed.config, original);
  const record = JSON.parse(receipt);
  record.runtime.client.version = '1.19.4';
  await fs.writeFile(installed.receipt, JSON.stringify(record));
  await assert.rejects(installMcp('uninstall', f.query, f.context), { code: 'MCP_RECEIPT' });
  assert.deepEqual(await fs.readFile(installed.config), original);
});

test('V2 uninstall refuses edits that would remove adjacent JSONC comments', async t => {
  const f = await fixture(t), installed = await installMcp('setup', f.options, f.context);
  const changed = (await fs.readFile(installed.config, 'utf8'))
    .replace('"dll_doctor":', '// keep this note\n      "dll_doctor":');
  await fs.writeFile(installed.config, changed);
  await assert.rejects(installMcp('uninstall', f.query, f.context), { code: 'MCP_CONFIG' });
  assert.equal(await fs.readFile(installed.config, 'utf8'), changed);
  assert.ok(await fs.stat(installed.receipt));
});
