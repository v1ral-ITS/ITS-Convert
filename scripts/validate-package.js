#!/usr/bin/env node

const fs = require("node:fs");

if (!fs.existsSync("bin/itsconvert.js")) {
  console.error("Error: bin/itsconvert.js not found");
  process.exit(1);
}
