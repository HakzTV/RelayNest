const { spawnSync } = require('node:child_process');
const { existsSync } = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const venvPython = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const candidates = process.platform === 'win32'
  ? [['python'], ['py', '-3']]
  : [['python3'], ['python']];

function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, stdio: 'inherit' });
  if (result.error || result.status !== 0) {
    console.error(`Failed to run ${command}: ${result.error ? result.error.message : `exit code ${result.status}`}`);
    process.exit(result.status || 1);
  }
}

if (!existsSync(venvPython)) {
  const python = candidates.find(([command, ...args]) => {
    const result = spawnSync(command, [...args, '--version'], { cwd: root, stdio: 'ignore' });
    return !result.error && result.status === 0;
  });
  if (!python) {
    console.error('Python 3 is required. Install Python and make it available on your PATH, then run npm install again.');
    process.exit(1);
  }
  console.log('Creating the project Python environment...');
  run(python[0], [...python.slice(1), '-m', 'venv', '.venv']);
}

console.log('Installing Python desktop requirements (including requirements.txt)...');
run(venvPython, ['-m', 'pip', 'install', '-r', 'requirements-desktop.txt']);
