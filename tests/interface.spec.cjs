const { test, expect, chromium } = require('@playwright/test');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
let browser, page;

test.beforeEach(async () => {
  browser = await chromium.launch({ channel: 'msedge', headless: true });
  page = await browser.newPage({ viewport: { width: 1280, height: 850 } });
  await page.addInitScript(() => {
    window.relayTestEvents = [];
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: async text => { window.copiedAddress = text; } }, configurable: true });
    window.pywebview = { api: { choose_folder: async () => 'C:\\test-folder', start: async () => ({ ok: true }), stop: async () => true, poll: async () => window.relayTestEvents.splice(0) } };
  });
  await page.goto(pathToFileURL(path.join(__dirname, '..', 'desktop', 'index.html')).href);
});
test.afterEach(async () => { await browser.close(); });

test('direction, activity and session settings follow the design', async () => {
  await expect(page.getByRole('heading', { name: 'Transfer files' })).toBeVisible();
  await expect(page.getByText('Sending device', { exact: true })).toBeVisible();
  await page.screenshot({ path: 'test-results/relaynest-interface.png' });
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await expect(page.getByText('Receiving device', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Folder to share')).toBeVisible();
  await expect(page.getByText(/Anyone who can reach/)).toBeVisible();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Light', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.getByRole('button', { name: 'Dark', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByLabel('Default port').fill('9000');
  await page.getByLabel('Default port').blur();
  await page.getByRole('button', { name: 'Activity', exact: true }).click();
  await expect(page.getByText('Transfer details will appear here.')).toBeVisible();
  await page.getByRole('button', { name: 'Transfer', exact: true }).click();
  await expect(page.getByLabel('Port', { exact: true })).toHaveValue('9000');
});

test('validation is visible and folder chooser populates destination', async () => {
  await page.getByRole('button', { name: 'Start transfer' }).click();
  await expect(page.getByRole('alert')).toHaveText('Enter a source address and destination folder.');
  await page.getByRole('button', { name: 'Browse', exact: true }).click();
  await expect(page.getByLabel('Destination folder', { exact: true })).toHaveValue('C:\\test-folder');
});


test('control height and bottom settings stay consistent', async () => {
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  const port = page.getByLabel('Port', { exact: true });
  const folder = page.getByLabel('Folder to share');
  expect((await port.boundingBox()).height).toBe((await folder.boundingBox()).height);
  await expect(page.getByText('A simple space for moving files between your devices.')).toHaveCount(0);
  const settings = page.getByRole('button', { name: 'Settings', exact: true });
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect(settings).toBeInViewport();
});


test('share address and real activity events drive the device flow', async () => {
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await page.evaluate(() => window.relayTestEvents.push({ type: 'share_ready', addresses: ['192.168.1.8', '10.0.0.2'], port: 8000 }));
  await expect(page.getByLabel('Share address', { exact: true })).toHaveValue('http://192.168.1.8:8000/');
  await page.getByLabel('Network address').selectOption('http://10.0.0.2:8000/');
  await expect(page.getByLabel('Share address', { exact: true })).toHaveValue('http://10.0.0.2:8000/');
  await page.getByRole('button', { name: 'Copy', exact: true }).click();
  await expect.poll(() => page.evaluate(() => window.copiedAddress)).toBe('http://10.0.0.2:8000/');
  await page.evaluate(() => window.relayTestEvents.push({ type: 'peer_activity', address: '10.0.0.3', active: 1 }));
  await expect(page.locator('#connectionStatus')).toContainText('10.0.0.3 is accessing');
  await expect(page.locator('#rightNode')).toHaveClass(/selected/);
  await page.evaluate(() => window.relayTestEvents.push({ type: 'peer_activity', address: '10.0.0.3', active: 0 }));
  await expect(page.locator('#connectionStatus')).toContainText('Last request from 10.0.0.3');
  await expect(page.locator('#rightNode')).not.toHaveClass(/selected/);
  await page.evaluate(() => window.relayTestEvents.push({ type: 'finished', stopped: true, code: null }));
  await expect(page.locator('#shareInfo')).toBeHidden();
});
