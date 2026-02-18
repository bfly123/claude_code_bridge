import _build from "../../core/build/index.js";
import { printHelp } from "../../core/messages.js";
import { flagsToAstroInlineConfig } from "../flags.js";
async function build({ flags }) {
  if (flags?.help || flags?.h) {
    printHelp({
      commandName: "astro build",
      usage: "[...flags]",
      tables: {
        Flags: [
          ["--outDir <directory>", `Specify the output directory for the build.`],
          [
            "--force",
            "Clear the content layer and content collection cache, forcing a full rebuild."
          ],
          ["--help (-h)", "See all available flags."]
        ]
      },
      description: `Builds your site for deployment.`
    });
    return;
  }
  const inlineConfig = flagsToAstroInlineConfig(flags);
  await _build(inlineConfig);
}
export {
  build
};
