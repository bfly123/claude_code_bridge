import { cyan } from "kleur/colors";
import devServer from "../../core/dev/index.js";
import { printHelp } from "../../core/messages.js";
import { flagsToAstroInlineConfig } from "../flags.js";
async function dev({ flags }) {
  if (flags.help || flags.h) {
    printHelp({
      commandName: "astro dev",
      usage: "[...flags]",
      tables: {
        Flags: [
          ["--port", `Specify which port to run on. Defaults to 4321.`],
          ["--host", `Listen on all addresses, including LAN and public addresses.`],
          ["--host <custom-address>", `Expose on a network IP address at <custom-address>`],
          ["--open", "Automatically open the app in the browser on server start"],
          ["--force", "Clear the content layer cache, forcing a full rebuild."],
          ["--help (-h)", "See all available flags."]
        ]
      },
      description: `Check ${cyan(
        "https://docs.astro.build/en/reference/cli-reference/#astro-dev"
      )} for more information.`
    });
    return;
  }
  const inlineConfig = flagsToAstroInlineConfig(flags);
  return await devServer(inlineConfig);
}
export {
  dev
};
