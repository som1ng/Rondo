import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import net from 'node:net';
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { setTimeout as delay } from 'node:timers/promises';

const { chromium } = createRequire(import.meta.url)(process.env.DLL_GUI_PLAYWRIGHT || 'playwright');
assert.equal(process.argv.length, 3, 'Pass the relocated Rondo.exe path');
const gui = await fs.realpath(process.argv[2]);
const listener = net.createServer();
listener.listen(0, '127.0.0.1');
await once(listener, 'listening');
const port = listener.address().port;
await new Promise(resolve => listener.close(resolve));
const profile = await fs.mkdtemp(path.join(os.tmpdir(), 'rondo-webview-'));
const child = spawn(gui, [], { cwd: path.dirname(gui), windowsHide: false, stdio: 'ignore',
  env: { ...process.env, TEMP: profile, TMP: profile,
    WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: `--remote-debugging-port=${port} --remote-debugging-address=127.0.0.1` } });
let ended = false, launchError, browser;
child.once('error', error => { launchError = error; });
const closed = new Promise(resolve => child.once('close', code => { ended = true; resolve(code); }));
try {
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    if (launchError) throw launchError;
    assert.equal(ended, false, 'GUI exited before WebView2 initialized');
    try { browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`, { timeout: 1000 }); break; }
    catch { await delay(200); }
  }
  assert.ok(browser, 'The relocated GUI did not initialize WebView2');
  const context = browser.contexts()[0];
  const page = context.pages()[0] || await context.waitForEvent('page', { timeout: 10000 });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.waitForFunction(() => typeof state !== 'undefined' && state.processes.length > 0, null, { timeout: 15000 });
  const count = await page.evaluate(() => state.processes.length);
  assert.equal(await page.locator('#btnRefreshProcesses').isVisible(), true);
  assert.deepEqual(errors, []);
  await page.locator('.win-btn.close').click();
  const code = await Promise.race([closed, delay(10000, undefined, { ref: false }).then(() => { throw new Error('GUI did not close'); })]);
  assert.equal(code, 0);
  console.log(JSON.stringify({ status: 'success', webview_initialized: true, process_count: count, native_close: true }));
} finally {
  await browser?.close().catch(() => {});
  if (!ended) { child.kill(); await closed; }
  await fs.rm(profile, { recursive: true, maxRetries: 20, retryDelay: 50 });
}
