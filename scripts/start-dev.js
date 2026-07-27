const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");
const { spawn } = require("node:child_process");

const rootDir = path.resolve(__dirname, "..");
const npmExecPath = process.env.npm_execpath;
const preferredBackendPort = Number(process.env.PORT || 1338);

if (!npmExecPath) {
  throw new Error("npm_execpath is not available. Please run this script via `npm run dev`.");
}

function isPortAvailable(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => {
      server.close(() => resolve(true));
    });
    server.listen(port, "127.0.0.1");
  });
}

async function pickBackendPort(startPort) {
  for (let port = startPort; port < startPort + 20; port += 1) {
    if (await isPortAvailable(port)) {
      return port;
    }
  }
  throw new Error(`No available backend port found in range ${startPort}-${startPort + 19}.`);
}
const services = [
  {
    name: "backend",
    cwd: path.join(rootDir, "backend"),
    script: "develop",
    marker: path.join("node_modules", "@strapi", "strapi", "package.json"),
    env: {},
  },
  {
    name: "frontend",
    cwd: path.join(rootDir, "frontend"),
    script: "dev",
    marker: path.join("node_modules", "next", "package.json"),
    env: {},
  },
];

function runNpmCommand(args, cwd, extraEnv) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [npmExecPath, ...args], {
      cwd,
      stdio: "inherit",
      env: {
        ...process.env,
        ...extraEnv,
      },
    });
    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`npm ${args.join(" ")} failed with code ${code}`));
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
    await runNpmCommand(["install"], service.cwd);
  }
}

function startServices(backendPort) {
  const strapiUrl = process.env.NEXT_PUBLIC_STRAPI_URL || `http://localhost:${backendPort}`;

  const runtimeServices = services.map((service) => ({
    ...service,
    env:
      service.name === "backend"
        ? { ...service.env, PORT: String(backendPort) }
        : { ...service.env, NEXT_PUBLIC_STRAPI_URL: strapiUrl },
  }));

  const children = runtimeServices.map((service) =>
    spawn(process.execPath, [npmExecPath, "run", service.script], {
      cwd: service.cwd,
      stdio: "inherit",
      env: {
        ...process.env,
        ...service.env,
      },
    })
  );

  console.log(`[dev] Backend admin: ${strapiUrl}/admin`);

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
  .then(() => pickBackendPort(preferredBackendPort))
  .then(startServices)
  .catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
