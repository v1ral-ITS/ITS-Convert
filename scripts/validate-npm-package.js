'use strict';

const fs = require('node:fs');
const path = require('node:path');

for (const relative of ['bin/itsconvert.js', 'itsconvert/cli.py', 'pyproject.toml']) {
  if (!fs.existsSync(path.resolve(__dirname, '..', relative))) {
    throw new Error(`npm package is missing required file: ${relative}`);
  }
}
