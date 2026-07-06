#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const path = require("node:path");

const packageRoot = path.resolve(__dirname, "..");
const pythonLaunchers = process.platform === "win32"
  ? [["py", ["-3"]], ["python", []], ["python3", []]]
  : [["python3", []], ["python", []], ["py", ["-3"]]];

function pythonEnv() {
  return {
    ...process.env,
    PYTHONPATH: process.env.PYTHONPATH
      ? `${packageRoot}${path.delimiter}${process.env.PYTHONPATH}`
      : packageRoot,
  };
}

function findPython() {
  for (const [command, baseArgs] of pythonLaunchers) {
    const probe = spawnSync(command, [...baseArgs, "--version"], {
      stdio: "ignore",
    });
    if (probe.status === 0) {
      return [command, baseArgs];
    }
  }
  return null;
}

function commandLabel(command, baseArgs) {
  return [command, ...baseArgs].join(" ");
}

const launcher = findPython();
if (!launcher) {
  console.error("ITS-Convert requires Python 3.11+ to run.");
  process.exit(1);
}

const [command, baseArgs] = launcher;
const env = pythonEnv();
const dependencyCheck = spawnSync(command, [...baseArgs, "-c", "import pydantic, rich, typer"], {
  cwd: packageRoot,
  env,
  stdio: "ignore",
});

if (dependencyCheck.status !== 0) {
  console.error("ITS-Convert requires Python dependencies before the npm launcher can run.");
  console.error(`Install them with:\n  ${commandLabel(command, baseArgs)} -m pip install pydantic rich typer`);
  process.exit(dependencyCheck.status || 1);
}

const result = spawnSync(command, [...baseArgs, "-m", "itsconvert.cli", ...process.argv.slice(2)], {
  cwd: packageRoot,
  env,
  stdio: "inherit",
});

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}

process.exit(result.status ?? 1);
