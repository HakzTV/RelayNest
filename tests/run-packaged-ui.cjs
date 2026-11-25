const { spawnSync } = require('node:child_process');
const path = require('node:path');
const root = path.join(__dirname, '..');
const app = path.join(root, 'dist', 'RelayNest.exe');
const runner = path.join(root, 'node_modules', '@playwright', 'test', 'cli.js');
const result = spawnSync(process.execPath, [runner, 'test', 'tests/desktop.spec.cjs', '--workers=1'], {
  cwd: root,
  env: { ...process.env, RELAYNEST_TEST_EXECUTABLE: app },
  stdio: 'inherit'
});
if (result.error) { console.error(result.error.message); process.exit(1); }
process.exit(result.status === null ? 1 : result.status);
