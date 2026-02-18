import { createRequire } from "node:module";
import boxen from "boxen";
import ci from "ci-info";
import { bold, cyan, dim, magenta } from "kleur/colors";
import ora from "ora";
import preferredPM from "preferred-pm";
import prompts from "prompts";
import whichPm from "which-pm";
import { exec } from "./exec.js";
const require2 = createRequire(import.meta.url);
async function getPackage(packageName, logger, options, otherDeps = []) {
  try {
    require2.resolve(packageName, { paths: [options.cwd ?? process.cwd()] });
    const packageImport = await import(packageName);
    return packageImport;
  } catch {
    if (options.optional) return void 0;
    let message = `To continue, Astro requires the following dependency to be installed: ${bold(
      packageName
    )}.`;
    if (ci.isCI) {
      message += ` Packages cannot be installed automatically in CI environments.`;
    }
    logger.info("SKIP_FORMAT", message);
    if (ci.isCI) {
      return void 0;
    }
    const result = await installPackage([packageName, ...otherDeps], options, logger);
    if (result) {
      const packageImport = await import(packageName);
      return packageImport;
    } else {
      return void 0;
    }
  }
}
function getInstallCommand(packages, packageManager) {
  switch (packageManager) {
    case "npm":
      return { pm: "npm", command: "install", flags: [], dependencies: packages };
    case "yarn":
      return { pm: "yarn", command: "add", flags: [], dependencies: packages };
    case "pnpm":
      return { pm: "pnpm", command: "add", flags: [], dependencies: packages };
    case "bun":
      return { pm: "bun", command: "add", flags: [], dependencies: packages };
    default:
      return null;
  }
}
async function getExecCommand(packageManager) {
  if (!packageManager) {
    packageManager = (await preferredPM(process.cwd()))?.name ?? "npm";
  }
  switch (packageManager) {
    case "npm":
      return "npx";
    case "yarn":
      return "yarn dlx";
    case "pnpm":
      return "pnpm dlx";
    case "bun":
      return "bunx";
    default:
      return "npx";
  }
}
async function installPackage(packageNames, options, logger) {
  const cwd = options.cwd ?? process.cwd();
  const packageManager = (await whichPm(cwd))?.name ?? "npm";
  const installCommand = getInstallCommand(packageNames, packageManager);
  if (!installCommand) {
    return false;
  }
  const coloredOutput = `${bold(installCommand.pm)} ${installCommand.command}${[
    "",
    ...installCommand.flags
  ].join(" ")} ${cyan(installCommand.dependencies.join(" "))}`;
  const message = `
${boxen(coloredOutput, {
    margin: 0.5,
    padding: 0.5,
    borderStyle: "round"
  })}
`;
  logger.info(
    "SKIP_FORMAT",
    `
  ${magenta("Astro will run the following command:")}
  ${dim(
      "If you skip this step, you can always run it yourself later"
    )}
${message}`
  );
  let response;
  if (options.skipAsk) {
    response = true;
  } else {
    response = (await prompts({
      type: "confirm",
      name: "askToContinue",
      message: "Continue?",
      initial: true
    })).askToContinue;
  }
  if (Boolean(response)) {
    const spinner = ora("Installing dependencies...").start();
    try {
      await exec(
        installCommand.pm,
        [installCommand.command, ...installCommand.flags, ...installCommand.dependencies],
        {
          nodeOptions: {
            cwd,
            // reset NODE_ENV to ensure install command run in dev mode
            env: { NODE_ENV: void 0 }
          }
        }
      );
      spinner.succeed();
      return true;
    } catch (err) {
      logger.debug("add", "Error installing dependencies", err);
      spinner.fail();
      return false;
    }
  } else {
    return false;
  }
}
async function fetchPackageJson(scope, name, tag) {
  const packageName = `${scope ? `${scope}/` : ""}${name}`;
  const registry = await getRegistry();
  const res = await fetch(`${registry}/${packageName}/${tag}`);
  if (res.status >= 200 && res.status < 300) {
    return await res.json();
  } else if (res.status === 404) {
    return new Error();
  } else {
    return new Error(`Failed to fetch ${registry}/${packageName}/${tag} - GET ${res.status}`);
  }
}
async function fetchPackageVersions(packageName) {
  const registry = await getRegistry();
  const res = await fetch(`${registry}/${packageName}`, {
    headers: { accept: "application/vnd.npm.install-v1+json" }
  });
  if (res.status >= 200 && res.status < 300) {
    return await res.json().then((data) => Object.keys(data.versions));
  } else if (res.status === 404) {
    return new Error();
  } else {
    return new Error(`Failed to fetch ${registry}/${packageName} - GET ${res.status}`);
  }
}
let _registry;
async function getRegistry() {
  if (_registry) return _registry;
  const fallback = "https://registry.npmjs.org";
  const packageManager = (await preferredPM(process.cwd()))?.name || "npm";
  try {
    const { stdout } = await exec(packageManager, ["config", "get", "registry"]);
    _registry = stdout.trim()?.replace(/\/$/, "") || fallback;
    if (!new URL(_registry).host) _registry = fallback;
  } catch {
    _registry = fallback;
  }
  return _registry;
}
export {
  fetchPackageJson,
  fetchPackageVersions,
  getExecCommand,
  getPackage
};
