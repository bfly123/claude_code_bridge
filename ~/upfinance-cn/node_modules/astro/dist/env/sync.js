import fsMod from "node:fs";
import { TYPES_TEMPLATE_URL } from "./constants.js";
import { getEnvFieldType } from "./validators.js";
function syncAstroEnv(settings, fs = fsMod) {
  if (!settings.config.experimental.env) {
    return;
  }
  const schema = settings.config.experimental.env.schema ?? {};
  let client = "";
  let server = "";
  for (const [key, options] of Object.entries(schema)) {
    const str = `export const ${key}: ${getEnvFieldType(options)};	
`;
    if (options.context === "client") {
      client += str;
    } else {
      server += str;
    }
  }
  const template = fs.readFileSync(TYPES_TEMPLATE_URL, "utf-8");
  const content = template.replace("// @@CLIENT@@", client).replace("// @@SERVER@@", server);
  settings.injectedTypes.push({
    filename: "astro/env.d.ts",
    content
  });
}
export {
  syncAstroEnv
};
