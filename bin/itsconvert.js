#!/usr/bin/env node
'use strict';

const { spawnSync } = require('node:child_process');
const path = require('node:path');

const projectRoot = path.resolve(__dirname, '..');
const candidates = process.env.ITSCONVERT_PYTHON
  ? [process.env.ITSCONVERT_PYTHON]
  : process.platform === 'win32' ? ['py', 'python'] : ['python3', 'python'];

for (const executable of candidates) {
  const env = { ...process.env };
  env.PYTHONPATH = [projectRoot, env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  const result = spawnSync(executable, ['-m', 'itsconvert.cli', ...process.argv.slice(2)], {
    env,
    stdio: 'inherit'
  });
  if (!result.error) process.exit(result.status ?? 1);
  if (result.error.code !== 'ENOENT') {
    console.error(`itsconvert: unable to start ${executable}: ${result.error.message}`);
    process.exit(1);
  }
}

console.error('itsconvert requires Python 3.11 or newer on PATH.');
console.error('Set ITSCONVERT_PYTHON to an explicit Python executable if needed.');
process.exit(1);
