import {
  NOOP_ACTIONS,
  RESOLVED_VIRTUAL_INTERNAL_MODULE_ID,
  RESOLVED_VIRTUAL_MODULE_ID,
  VIRTUAL_INTERNAL_MODULE_ID,
  VIRTUAL_MODULE_ID
} from "./consts.js";
import { isActionsFilePresent } from "./utils.js";
function vitePluginUserActions({ settings }) {
  let resolvedActionsId;
  return {
    name: "@astro/plugin-actions",
    async resolveId(id) {
      if (id === NOOP_ACTIONS) {
        return NOOP_ACTIONS;
      }
      if (id === VIRTUAL_INTERNAL_MODULE_ID) {
        const resolvedModule = await this.resolve(
          `${decodeURI(new URL("actions", settings.config.srcDir).pathname)}`
        );
        if (!resolvedModule) {
          return NOOP_ACTIONS;
        }
        resolvedActionsId = resolvedModule.id;
        return RESOLVED_VIRTUAL_INTERNAL_MODULE_ID;
      }
    },
    load(id) {
      if (id === NOOP_ACTIONS) {
        return "export const server = {}";
      } else if (id === RESOLVED_VIRTUAL_INTERNAL_MODULE_ID) {
        return `export { server } from '${resolvedActionsId}';`;
      }
    }
  };
}
function vitePluginActions({
  fs,
  settings
}) {
  return {
    name: VIRTUAL_MODULE_ID,
    enforce: "pre",
    resolveId(id) {
      if (id === VIRTUAL_MODULE_ID) {
        return RESOLVED_VIRTUAL_MODULE_ID;
      }
    },
    async configureServer(server) {
      const filePresentOnStartup = await isActionsFilePresent(fs, settings.config.srcDir);
      async function watcherCallback() {
        const filePresent = await isActionsFilePresent(fs, settings.config.srcDir);
        if (filePresentOnStartup !== filePresent) {
          server.restart();
        }
      }
      server.watcher.on("add", watcherCallback);
      server.watcher.on("change", watcherCallback);
    },
    async load(id, opts) {
      if (id !== RESOLVED_VIRTUAL_MODULE_ID) return;
      let code = await fs.promises.readFile(
        new URL("../../templates/actions.mjs", import.meta.url),
        "utf-8"
      );
      if (opts?.ssr) {
        code += `
export * from 'astro/actions/runtime/virtual/server.js';`;
      } else {
        code += `
export * from 'astro/actions/runtime/virtual/client.js';`;
      }
      return code;
    }
  };
}
export {
  vitePluginActions,
  vitePluginUserActions
};
