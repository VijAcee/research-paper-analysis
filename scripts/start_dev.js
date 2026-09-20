const { spawn } = require('child_process');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');

console.log('===========================================================');
console.log('  PAPERLENS UNIFIED DEV SERVER LAUNCHER');
console.log('===========================================================');
console.log('[1/2] Launching Python FastAPI Backend (http://localhost:8000)...');

const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
const backendProcess = spawn(pythonCmd, ['backend/keep_backend_alive.py'], {
  cwd: rootDir,
  stdio: 'inherit',
  shell: true
});

console.log('[2/2] Launching Next.js Workspace Frontend (http://localhost:3000)...');

const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const frontendProcess = spawn(npmCmd, ['run', 'dev', '--prefix', 'frontend'], {
  cwd: rootDir,
  stdio: 'inherit',
  shell: true
});

function shutdown() {
  console.log('\n[LAUNCHER] Terminating server processes...');
  try { backendProcess.kill(); } catch (e) {}
  try { frontendProcess.kill(); } catch (e) {}
  process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
process.on('exit', shutdown);
