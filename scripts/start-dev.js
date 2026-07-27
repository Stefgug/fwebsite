const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");

const rootDir = path.resolve(__dirname, "..");
const services = [
  {
    name: "backend",
    cwd: path.join(rootDir, "backend"),
    script: "develop",
    marker: path.join("node_modules", "@strapi", "strapi", "package.json"),
  },
  {
    name: "frontend",
    cwd: path.join(rootDir, "frontend"),
    script: "dev",
    marker: path.join("node_modules", "next", "package.json"),
  },
];

function runCommand(command, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, { cwd, stdio: "inherit", shell: true });
    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`${command} failed with code ${code}`));
    });
    child.on("error", reject);
  });
}

async function ensureDependencies() {
  for (const service of services) {
    const markerPath = path.join(service.cwd, service.marker);
    if (fs.existsSync(markerPath)) {
      continue;
    }

    console.log(`[setup] Installing ${service.name} dependencies...`);
    await runCommand("npm install", service.cwd);
  }
}

function startServices() {
  const children = services.map((service) =>
    spawn(`npm run ${service.script}`, {
      cwd: service.cwd,
      stdio: "inherit",
      shell: true,
    })
  );

  let shuttingDown = false;

  const stopAll = () => {
    if (shuttingDown) {
      return;
    }
    shuttingDown = true;
    for (const child of children) {
      if (!child.killed) {
        child.kill("SIGINT");
      }
    }
  };

  for (const child of children) {
    child.on("exit", (code) => {
      if (!shuttingDown) {
        const exitCode = code === 0 ? 1 : (code ?? 1);
        console.error(`One service stopped (exit code ${exitCode}). Shutting down the other service.`);
        stopAll();
        process.exit(exitCode);
      }
    });
    child.on("error", (error) => {
      console.error(error.message);
      stopAll();
      process.exit(1);
    });
  }

  process.on("SIGINT", () => {
    stopAll();
    process.exit(0);
  });
  process.on("SIGTERM", () => {
    stopAll();
    process.exit(0);
  });
}

ensureDependencies()
  .then(startServices)
  .catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
