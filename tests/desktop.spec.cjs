const { test, expect, chromium } = require('@playwright/test');
const { spawn } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const net = require('node:net');
const http = require('node:http');

async function unusedPort() {
  const server = net.createServer();
  await new Promise((resolve, reject) => server.once('error', reject).listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  return port;
}

async function openDesktop() {
  const root = path.join(__dirname, '..');
  const venvPython = path.join(root, '.venv', 'Scripts', 'python.exe');
  const python = process.env.RELAYNEST_PYTHON || (fs.existsSync(venvPython) ? venvPython : 'python');
  const port = await unusedPort();
  const packaged = process.env.RELAYNEST_TEST_EXECUTABLE;
  const executable = packaged || python;
  const args = packaged ? [] : ['-u', path.join(root, 'desktop_host.py')];
  const child = spawn(executable, args, {
    cwd: root, env: { ...process.env, RELAYNEST_WEBVIEW_DEBUG_PORT: String(port) }, windowsHide: true
  });
  let output = '';
  let launchError;
  child.on('error', error => { launchError = error; });
  child.stdout.on('data', d => { output += d.toString(); });
  child.stderr.on('data', d => { output += d.toString(); });
  let browser;
  try {
    for (let attempt = 0; attempt < 100; attempt++) {
      if (launchError) throw new Error(`Unable to start ${executable}: ${launchError.message}`);
      if (child.exitCode !== null) throw new Error(`Desktop exited: ${output}`);
      try { browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`, { timeout: 1000 }); break; }
      catch { await new Promise(resolve => setTimeout(resolve, 300)); }
    }
    if (!browser) throw new Error(`Could not connect to WebView2. ${output}`);
    let page;
    for (let attempt = 0; attempt < 40 && !page; attempt++) {
      page = browser.contexts().flatMap(context => context.pages()).find(item => item.url().includes('index.html'));
      if (!page) await new Promise(resolve => setTimeout(resolve, 250));
    }
    if (!page) throw new Error('RelayNest page was not found in the desktop window.');
    return { browser, child, page };
  } catch (error) {
    if (browser) await browser.close();
    child.kill();
    throw error;
  }
}

test('desktop receive and send controls validate input', async () => {
  test.skip(process.platform !== 'win32', 'Desktop WebView2 CDP test requires Windows.');
  test.setTimeout(60000);
  const { browser, child, page } = await openDesktop();
  try {
    await expect(page.getByRole('heading', { name: 'Transfer files' })).toBeVisible();
    await page.getByRole('button', { name: 'Start transfer' }).click();
    await expect(page.getByText('Enter a source address and destination folder.')).toBeVisible();
    await page.getByRole('button', { name: 'Send', exact: true }).click();
    await expect(page.getByLabel('Folder to share')).toBeVisible();
    await expect(page.getByText(/Anyone who can reach/)).toBeVisible();
  } finally { await browser.close(); child.kill(); }
});

test('desktop shares and receives actual files', async () => {
  test.skip(process.platform !== 'win32', 'Desktop WebView2 CDP test requires Windows.');
  test.setTimeout(90000);
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'relaynest-desktop-test-'));
  const source = path.join(temp, 'source');
  const destination = path.join(temp, 'destination');
  fs.mkdirSync(source); fs.mkdirSync(destination);
  fs.writeFileSync(path.join(source, 'sample.txt'), 'from RelayNest');
  const sourcePort = await unusedPort();
  let desktop;
  let httpServer;
  try {
    desktop = await openDesktop();
    const { page } = desktop;
    await page.getByRole('button', { name: 'Send', exact: true }).click();
    await page.getByLabel('Folder to share').fill(source);
    await page.getByLabel('Port', { exact: true }).fill(String(sourcePort));
    await page.getByRole('button', { name: 'Start sharing' }).click();
    await expect(page.getByRole('button', { name: 'Stop sharing' })).toBeVisible();
    await expect(page.locator('#shareInfo')).toBeVisible();
    await expect(page.locator('#connectionStatus')).toContainText('Waiting for a device');
    await expect.poll(async () => {
      try { return await (await fetch(`http://127.0.0.1:${sourcePort}/sample.txt`)).text(); }
      catch { return ''; }
    }, { timeout: 30000 }).toBe('from RelayNest');
    await expect(page.locator('#connectionStatus')).toContainText('Last request from 127.0.0.1');
    await page.getByRole('button', { name: 'Stop sharing' }).click();
    await expect(page.locator('#shareInfo')).toBeHidden();
    await expect(page.getByRole('button', { name: 'Start sharing' })).toBeEnabled({ timeout: 30000 });

    const body = Buffer.from('received from server');
    httpServer = http.createServer((req, res) => {
      if (req.url === '/') { res.writeHead(200, { 'Content-Type': 'text/html' }); res.end('<title>Directory listing for /</title><a href="sample.txt">sample.txt</a>'); return; }
      if (req.url === '/sample.txt') { res.writeHead(200, { 'Content-Length': body.length, 'Last-Modified': 'Wed, 21 Oct 2015 07:28:00 GMT' }); res.end(req.method === 'HEAD' ? undefined : body); return; }
      res.writeHead(404); res.end();
    });
    await new Promise(resolve => httpServer.listen(0, '127.0.0.1', resolve));
    await page.getByRole('button', { name: 'Receive', exact: true }).click();
    await page.getByLabel('Source address').fill(`http://127.0.0.1:${httpServer.address().port}/`);
    await page.getByLabel('Destination folder', { exact: true }).fill(destination);
    await page.getByRole('button', { name: 'Start transfer' }).click();
    await expect(page.locator('#stateBadge')).toHaveText('Completed', { timeout: 30000 });
    expect(fs.readFileSync(path.join(destination, 'sample.txt'), 'utf8')).toBe('received from server');
    await page.getByRole('button', { name: 'Activity', exact: true }).click();
    await expect(page.locator('#log')).toContainText('Completed:');
  } finally {
    if (httpServer) await new Promise(resolve => httpServer.close(resolve));
    if (desktop) { await desktop.browser.close(); desktop.child.kill(); }
    const relative = path.relative(os.tmpdir(), temp);
    if (!relative.startsWith('relaynest-desktop-test-') || relative.includes(path.sep) || path.isAbsolute(relative)) throw new Error('Unexpected temporary directory path');
    fs.rmSync(temp, { recursive: true, force: true });
  }
});
