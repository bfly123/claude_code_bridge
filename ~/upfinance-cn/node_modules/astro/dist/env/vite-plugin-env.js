import { fileURLToPath } from "node:url";
import { loadEnv } from "vite";
import { AstroError, AstroErrorData } from "../core/errors/index.js";
import {
  MODULE_TEMPLATE_URL,
  VIRTUAL_MODULES_IDS,
  VIRTUAL_MODULES_IDS_VALUES
} from "./constants.js";
import { invalidVariablesToError } from "./errors.js";
import { getEnvFieldType, validateEnvVariable } from "./validators.js";
function astroEnv({
  settings,
  mode,
  fs,
  sync
}) {
  if (!settings.config.experimental.env) {
    return;
  }
  const schema = settings.config.experimental.env.schema ?? {};
  let templates = null;
  return {
    name: "astro-env-plugin",
    enforce: "pre",
    buildStart() {
      const loadedEnv = loadEnv(
        mode === "dev" ? "development" : "production",
        fileURLToPath(settings.config.root),
        ""
      );
      for (const [key, value] of Object.entries(loadedEnv)) {
        if (value !== void 0) {
          process.env[key] = value;
        }
      }
      const validatedVariables = validatePublicVariables({
        schema,
        loadedEnv,
        validateSecrets: settings.config.experimental.env?.validateSecrets ?? false,
        sync
      });
      templates = {
        ...getTemplates(schema, fs, validatedVariables),
        internal: `export const schema = ${JSON.stringify(schema)};`
      };
    },
    buildEnd() {
      templates = null;
    },
    resolveId(id) {
      if (VIRTUAL_MODULES_IDS_VALUES.has(id)) {
        return resolveVirtualModuleId(id);
      }
    },
    load(id, options) {
      if (id === resolveVirtualModuleId(VIRTUAL_MODULES_IDS.client)) {
        return templates.client;
      }
      if (id === resolveVirtualModuleId(VIRTUAL_MODULES_IDS.server)) {
        if (options?.ssr) {
          return templates.server;
        }
        throw new AstroError({
          ...AstroErrorData.ServerOnlyModule,
          message: AstroErrorData.ServerOnlyModule.message(VIRTUAL_MODULES_IDS.server)
        });
      }
      if (id === resolveVirtualModuleId(VIRTUAL_MODULES_IDS.internal)) {
        return templates.internal;
      }
    }
  };
}
function resolveVirtualModuleId(id) {
  return `\0${id}`;
}
function validatePublicVariables({
  schema,
  loadedEnv,
  validateSecrets,
  sync
}) {
  const valid = [];
  const invalid = [];
  for (const [key, options] of Object.entries(schema)) {
    const variable = loadedEnv[key] === "" ? void 0 : loadedEnv[key];
    if (options.access === "secret" && !validateSecrets) {
      continue;
    }
    const result = validateEnvVariable(variable, options);
    const type = getEnvFieldType(options);
    if (!result.ok) {
      invalid.push({ key, type, errors: result.errors });
    } else if (options.access === "public") {
      valid.push({ key, value: result.value, type, context: options.context });
    }
  }
  if (invalid.length > 0 && !sync) {
    throw new AstroError({
      ...AstroErrorData.EnvInvalidVariables,
      message: AstroErrorData.EnvInvalidVariables.message(invalidVariablesToError(invalid))
    });
  }
  return valid;
}
function getTemplates(schema, fs, validatedVariables) {
  let client = "";
  let server = fs.readFileSync(MODULE_TEMPLATE_URL, "utf-8");
  let onSetGetEnv = "";
  for (const { key, value, context } of validatedVariables) {
    const str = `export const ${key} = ${JSON.stringify(value)};`;
    if (context === "client") {
      client += str;
    } else {
      server += str;
    }
  }
  for (const [key, options] of Object.entries(schema)) {
    if (!(options.context === "server" && options.access === "secret")) {
      continue;
    }
    server += `export let ${key} = _internalGetSecret(${JSON.stringify(key)});
`;
    onSetGetEnv += `${key} = reset ? undefined : _internalGetSecret(${JSON.stringify(key)});
`;
  }
  server = server.replace("// @@ON_SET_GET_ENV@@", onSetGetEnv);
  return {
    client,
    server
  };
}
export {
  astroEnv
};
