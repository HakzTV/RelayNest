/* Capture the actual source-based desktop window for the README on Windows. */
const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const net = require('node:net');
const path = require('node:path');

async function main() {
  if (process.platform !== 'win32') throw new Error('This capture uses Windows WebView2.');
  const root = path.resolve(__dirname, '..');
  const python = process.env.RELAYNEST_PYTHON || path.join(root, '.venv', 'Scripts', 'python.exe');
  const listener = net.createServer();
  await new Promise((resolve, reject) => listener.once('error', reject).listen(0, '127.0.0.1', resolve));
  const port = listener.address().port;
  await new Promise((resolve, reject) => listener.close(error => error ? reject(error) : resolve()));
  const child = spawn(python, ['-u', path.join(root, 'desktop_host.py')], {
    cwd: root,
    env: { ...process.env, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: `--remote-debugging-port=${port}` },
    windowsHide: true
  });
  let errorText = '';
  let launchError;
  child.on('error', error => { launchError = error; });
  child.stderr.on('data', data => { errorText += data.toString(); });
  let browser;
  try {
    for (let i = 0; i < 100; i++) {
      if (launchError) throw launchError;
      if (child.exitCode !== null) throw new Error(`Desktop exited: ${errorText}`);
      try { browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`, { timeout: 1000 }); break; }
      catch { await new Promise(resolve => setTimeout(resolve, 300)); }
    }
    if (!browser) throw new Error(`Unable to connect to the desktop WebView: ${errorText}`);
    let page;
    for (let i = 0; i < 40 && !page; i++) {
      page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('index.html'));
      if (!page) await new Promise(resolve => setTimeout(resolve, 250));
    }
    if (!page) throw new Error('Could not find the RelayNest desktop window.');
    await page.getByRole('heading', { name: 'Transfer files' }).waitFor();
    const destination = path.join(root, 'docs', 'screenshots');
    fs.mkdirSync(destination, { recursive: true });
    await page.screenshot({ path: path.join(destination, 'receive.png') });
    await page.getByRole('button', { name: 'Send', exact: true }).click();
    await page.screenshot({ path: path.join(destination, 'send.png') });
    await page.getByRole('button', { name: 'Settings', exact: true }).click();
    await page.getByRole('button', { name: 'Light', exact: true }).click();
    await page.screenshot({ path: path.join(destination, 'settings-light.png') });
    console.log('Captured the RelayNest desktop window in docs/screenshots.');
  } finally {
    if (browser) await browser.close();
    child.kill();
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
