const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");
const { spawn } = require("node:child_process");

const rootDir = path.resolve(__dirname, "..");
const npmExecPath = process.env.npm_execpath;
const preferredBackendPort = Number(process.env.PORT || 1338);
const preferredFrontendPort = Number(process.env.FRONTEND_PORT || 3000);

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
    // Bind on all interfaces so a port already taken on IPv6 (or on another
    // local interface) is correctly reported as unavailable.
    server.listen(port);
  });
}

async function pickPort(startPort, label) {
  for (let port = startPort; port < startPort + 20; port += 1) {
    if (await isPortAvailable(port)) {
      return port;
    }
  }
  throw new Error(`No available ${label} port found in range ${startPort}-${startPort + 19}.`);
}

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

function startServices({ backendPort, frontendPort }) {
  const strapiUrl = process.env.NEXT_PUBLIC_STRAPI_URL || `http://localhost:${backendPort}`;

  const runtimeServices = services.map((service) =>
    service.name === "backend"
      ? { ...service, args: ["run", service.script], env: { PORT: String(backendPort) } }
      : {
          ...service,
          args: ["run", service.script, "--", "-p", String(frontendPort)],
          env: { NEXT_PUBLIC_STRAPI_URL: strapiUrl },
        }
  );

  const children = runtimeServices.map((service) =>
    spawn(process.execPath, [npmExecPath, ...service.args], {
      cwd: service.cwd,
      stdio: "inherit",
      env: {
        ...process.env,
        ...service.env,
      },
    })
  );

  console.log("");
  console.log(`[dev] Site        : http://localhost:${frontendPort}`);
  console.log(`[dev] Strapi API  : ${strapiUrl}`);
  console.log(`[dev] Strapi admin: ${strapiUrl}/admin`);
  console.log("");

  let shuttingDown = false;

  const killTree = (child) => {
    if (child.killed || child.exitCode !== null || !child.pid) {
      return;
    }

    if (process.platform === "win32") {
      // child.kill() only terminates the npm wrapper, leaving the actual
      // Strapi/Next process alive and holding its port. Kill the whole tree.
      spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], {
        stdio: "ignore",
      });
      return;
    }

    child.kill("SIGINT");
  };

  const stopAll = () => {
    if (shuttingDown) {
      return;
    }
    shuttingDown = true;
    for (const child of children) {
      killTree(child);
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
  .then(async () => ({
    backendPort: await pickPort(preferredBackendPort, "backend"),
    frontendPort: await pickPort(preferredFrontendPort, "frontend"),
  }))
  .then(startServices)
  .catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
