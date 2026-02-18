import { execSync } from "node:child_process";
import { arch, platform } from "node:os";
import * as colors from "kleur/colors";
import prompts from "prompts";
import { resolveConfig } from "../../core/config/index.js";
import { ASTRO_VERSION } from "../../core/constants.js";
import { apply as applyPolyfill } from "../../core/polyfill.js";
import { flagsToAstroInlineConfig } from "../flags.js";
async function getInfoOutput({
  userConfig,
  print
}) {
  const rows = [
    ["Astro", `v${ASTRO_VERSION}`],
    ["Node", process.version],
    ["System", getSystem()],
    ["Package Manager", getPackageManager()]
  ];
  try {
    rows.push(["Output", userConfig.output ?? "static"]);
    rows.push(["Adapter", userConfig.adapter?.name ?? "none"]);
    const integrations = (userConfig?.integrations ?? []).filter(Boolean).flat().map((i) => i?.name).filter(Boolean);
    rows.push(["Integrations", integrations.length > 0 ? integrations : "none"]);
  } catch {
  }
  let output = "";
  for (const [label, value] of rows) {
    output += printRow(label, value, print);
  }
  return output.trim();
}
async function printInfo({ flags }) {
  applyPolyfill();
  const { userConfig } = await resolveConfig(flagsToAstroInlineConfig(flags), "info");
  const output = await getInfoOutput({ userConfig, print: true });
  await copyToClipboard(output);
}
async function copyToClipboard(text) {
  text = text.trim();
  const system = platform();
  let command = "";
  if (system === "darwin") {
    command = "pbcopy";
  } else if (system === "win32") {
    command = "clip";
  } else {
    const unixCommands = [
      ["xclip", "-sel clipboard -l 1"],
      ["wl-copy", '"$0"']
    ];
    for (const [unixCommand, args] of unixCommands) {
      try {
        const output = execSync(`which ${unixCommand}`, { encoding: "utf8", stdio: "pipe" });
        if (output[0] !== "/") {
          continue;
        }
        command = `${unixCommand} ${args}`;
      } catch {
        continue;
      }
    }
    if (!command) return;
  }
  console.log();
  const { shouldCopy } = await prompts({
    type: "confirm",
    name: "shouldCopy",
    message: "Copy to clipboard?",
    initial: true
  });
  if (!shouldCopy) return;
  try {
    execSync(command.replaceAll("$0", text), {
      stdio: "ignore",
      input: text,
      encoding: "utf8"
    });
  } catch {
    console.error(
      colors.red(`
Sorry, something went wrong!`) + ` Please copy the text above manually.`
    );
  }
}
const PLATFORM_TO_OS = {
  darwin: "macOS",
  win32: "Windows",
  linux: "Linux"
};
function getSystem() {
  const system = PLATFORM_TO_OS[platform()] ?? platform();
  return `${system} (${arch()})`;
}
function getPackageManager() {
  if (!process.env.npm_config_user_agent) {
    return "unknown";
  }
  const specifier = process.env.npm_config_user_agent.split(" ")[0];
  const name = specifier.substring(0, specifier.lastIndexOf("/"));
  return name === "npminstall" ? "cnpm" : name;
}
const MAX_PADDING = 25;
function printRow(label, value, print) {
  const padding = MAX_PADDING - label.length;
  const [first, ...rest] = Array.isArray(value) ? value : [value];
  let plaintext = `${label}${" ".repeat(padding)}${first}`;
  let richtext = `${colors.bold(label)}${" ".repeat(padding)}${colors.green(first)}`;
  if (rest.length > 0) {
    for (const entry of rest) {
      plaintext += `
${" ".repeat(MAX_PADDING)}${entry}`;
      richtext += `
${" ".repeat(MAX_PADDING)}${colors.green(entry)}`;
    }
  }
  plaintext += "\n";
  if (print) {
    console.log(richtext);
  }
  return plaintext;
}
export {
  getInfoOutput,
  printInfo
};
