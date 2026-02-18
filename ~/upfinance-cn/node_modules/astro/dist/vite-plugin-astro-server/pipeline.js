import { fileURLToPath } from "node:url";
import { getInfoOutput } from "../cli/info/index.js";
import { ASTRO_VERSION } from "../core/constants.js";
import { enhanceViteSSRError } from "../core/errors/dev/index.js";
import { AggregateError, CSSError, MarkdownError } from "../core/errors/index.js";
import { Pipeline, loadRenderer } from "../core/render/index.js";
import { createDefaultRoutes } from "../core/routing/default.js";
import { findRouteToRewrite } from "../core/routing/rewrite.js";
import { isPage, isServerLikeOutput, viteID } from "../core/util.js";
import { resolveIdToUrl } from "../core/viteUtils.js";
import { PAGE_SCRIPT_ID } from "../vite-plugin-scripts/index.js";
import { getStylesForURL } from "./css.js";
import { getComponentMetadata } from "./metadata.js";
import { createResolve } from "./resolve.js";
import { getScriptsForURL } from "./scripts.js";
class DevPipeline extends Pipeline {
  constructor(loader, logger, manifest, settings, config = settings.config, defaultRoutes = createDefaultRoutes(manifest)) {
    const mode = "development";
    const resolve = createResolve(loader, config.root);
    const serverLike = isServerLikeOutput(config);
    const streaming = true;
    super(logger, manifest, mode, [], resolve, serverLike, streaming);
    this.loader = loader;
    this.logger = logger;
    this.manifest = manifest;
    this.settings = settings;
    this.config = config;
    this.defaultRoutes = defaultRoutes;
    manifest.serverIslandMap = settings.serverIslandMap;
    manifest.serverIslandNameMap = settings.serverIslandNameMap;
  }
  // renderers are loaded on every request,
  // so it needs to be mutable here unlike in other environments
  renderers = new Array();
  manifestData;
  componentInterner = /* @__PURE__ */ new WeakMap();
  static create(manifestData, {
    loader,
    logger,
    manifest,
    settings
  }) {
    const pipeline = new DevPipeline(loader, logger, manifest, settings);
    pipeline.manifestData = manifestData;
    return pipeline;
  }
  async headElements(routeData) {
    const {
      config: { root },
      loader,
      mode,
      settings
    } = this;
    const filePath = new URL(`${routeData.component}`, root);
    const { scripts } = settings.config.experimental.directRenderScript ? { scripts: /* @__PURE__ */ new Set() } : await getScriptsForURL(filePath, settings.config.root, loader);
    if (isPage(filePath, settings) && mode === "development") {
      scripts.add({
        props: { type: "module", src: "/@vite/client" },
        children: ""
      });
      if (settings.config.devToolbar.enabled && await settings.preferences.get("devToolbar.enabled")) {
        const src = await resolveIdToUrl(loader, "astro/runtime/client/dev-toolbar/entrypoint.js");
        scripts.add({ props: { type: "module", src }, children: "" });
        const additionalMetadata = {
          root: fileURLToPath(settings.config.root),
          version: ASTRO_VERSION,
          latestAstroVersion: settings.latestAstroVersion,
          debugInfo: await getInfoOutput({ userConfig: settings.config, print: false })
        };
        const children = `window.__astro_dev_toolbar__ = ${JSON.stringify(additionalMetadata)}`;
        scripts.add({ props: {}, children });
      }
    }
    for (const script of settings.scripts) {
      if (script.stage === "head-inline") {
        scripts.add({
          props: {},
          children: script.content
        });
      } else if (script.stage === "page" && isPage(filePath, settings)) {
        scripts.add({
          props: { type: "module", src: `/@id/${PAGE_SCRIPT_ID}` },
          children: ""
        });
      }
    }
    const links = /* @__PURE__ */ new Set();
    const { urls, styles: _styles } = await getStylesForURL(filePath, loader);
    for (const href of urls) {
      links.add({ props: { rel: "stylesheet", href }, children: "" });
    }
    const styles = /* @__PURE__ */ new Set();
    for (const { id, url: src, content } of _styles) {
      scripts.add({ props: { type: "module", src }, children: "" });
      styles.add({ props: { "data-vite-dev-id": id }, children: content });
    }
    return { scripts, styles, links };
  }
  componentMetadata(routeData) {
    const {
      config: { root },
      loader
    } = this;
    const filePath = new URL(`${routeData.component}`, root);
    return getComponentMetadata(filePath, loader);
  }
  async preload(routeData, filePath) {
    const { loader } = this;
    for (const route of this.defaultRoutes) {
      if (route.matchesComponent(filePath)) {
        return route.instance;
      }
    }
    const renderers__ = this.settings.renderers.map((r) => loadRenderer(r, loader));
    const renderers_ = await Promise.all(renderers__);
    this.renderers = renderers_.filter((r) => Boolean(r));
    try {
      const componentInstance = await loader.import(viteID(filePath));
      this.componentInterner.set(routeData, componentInstance);
      return componentInstance;
    } catch (error) {
      if (MarkdownError.is(error) || CSSError.is(error) || AggregateError.is(error)) {
        throw error;
      }
      throw enhanceViteSSRError({ error, filePath, loader });
    }
  }
  clearRouteCache() {
    this.routeCache.clearAll();
    this.componentInterner = /* @__PURE__ */ new WeakMap();
  }
  async getComponentByRoute(routeData) {
    const component = this.componentInterner.get(routeData);
    if (component) {
      return component;
    } else {
      const filePath = new URL(`${routeData.component}`, this.config.root);
      return await this.preload(routeData, filePath);
    }
  }
  async tryRewrite(payload, request) {
    if (!this.manifestData) {
      throw new Error("Missing manifest data. This is an internal error, please file an issue.");
    }
    const { routeData, pathname, newUrl } = findRouteToRewrite({
      payload,
      request,
      routes: this.manifestData?.routes,
      trailingSlash: this.config.trailingSlash,
      buildFormat: this.config.build.format,
      base: this.config.base
    });
    const componentInstance = await this.getComponentByRoute(routeData);
    return { newUrl, pathname, componentInstance, routeData };
  }
  setManifestData(manifestData) {
    this.manifestData = manifestData;
  }
  rewriteKnownRoute(route, sourceRoute) {
    if (isServerLikeOutput(this.config) && sourceRoute.prerender) {
      for (let def of this.defaultRoutes) {
        if (route === def.route) {
          return def.instance;
        }
      }
    }
    throw new Error("Unknown route");
  }
}
export {
  DevPipeline
};
