import { pathToFileURL } from "node:url";
import { createServer } from "vite";
import loadFallbackPlugin from "../../vite-plugin-load-fallback/index.js";
import { debug } from "../logger/core.js";
async function createViteServer(root, fs) {
  const viteServer = await createServer({
    configFile: false,
    server: { middlewareMode: true, hmr: false, watch: null, ws: false },
    optimizeDeps: { noDiscovery: true },
    clearScreen: false,
    appType: "custom",
    ssr: {
      // NOTE: Vite doesn't externalize linked packages by default. During testing locally,
      // these dependencies trip up Vite's dev SSR transform. Awaiting upstream feature:
      // https://github.com/vitejs/vite/pull/10939
      external: [
        "@astrojs/tailwind",
        "@astrojs/mdx",
        "@astrojs/react",
        "@astrojs/preact",
        "@astrojs/sitemap",
        "@astrojs/markdoc",
        "@astrojs/db"
      ]
    },
    plugins: [loadFallbackPlugin({ fs, root: pathToFileURL(root) })]
  });
  return viteServer;
}
async function loadConfigWithVite({
  configPath,
  fs,
  root
}) {
  if (/\.[cm]?js$/.test(configPath)) {
    try {
      const config = await import(pathToFileURL(configPath).toString() + "?t=" + Date.now());
      return config.default ?? {};
    } catch (e) {
      debug("Failed to load config with Node", e);
    }
  }
  let server;
  try {
    server = await createViteServer(root, fs);
    const mod = await server.ssrLoadModule(configPath, { fixStacktrace: true });
    return mod.default ?? {};
  } finally {
    if (server) {
      await server.close();
    }
  }
}
export {
  loadConfigWithVite
};
