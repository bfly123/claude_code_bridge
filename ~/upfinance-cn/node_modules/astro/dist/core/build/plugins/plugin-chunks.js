import { extendManualChunks } from "./util.js";
function vitePluginChunks() {
  return {
    name: "astro:chunks",
    outputOptions(outputOptions) {
      extendManualChunks(outputOptions, {
        after(id) {
          if (id.includes("astro/dist/runtime/server/")) {
            return "astro/server";
          }
          if (id.includes("astro/dist/runtime")) {
            return "astro";
          }
          if (id.includes("astro/dist/env/setup")) {
            return "astro/env-setup";
          }
        }
      });
    }
  };
}
function pluginChunks() {
  return {
    targets: ["server"],
    hooks: {
      "build:before": () => {
        return {
          vitePlugin: vitePluginChunks()
        };
      }
    }
  };
}
export {
  pluginChunks,
  vitePluginChunks
};
