import fsMod from "node:fs";
import { fileURLToPath } from "node:url";
import { bold } from "kleur/colors";
import astroIntegrationActionsRouteHandler from "../actions/integration.js";
import { isActionsFilePresent } from "../actions/utils.js";
import { buildClientDirectiveEntrypoint } from "../core/client-directive/index.js";
import { mergeConfig } from "../core/config/index.js";
import { isServerLikeOutput } from "../core/util.js";
import { validateSupportedFeatures } from "./features-validation.js";
async function withTakingALongTimeMsg({
  name,
  hookName,
  hookResult,
  timeoutMs = 3e3,
  logger
}) {
  const timeout = setTimeout(() => {
    logger.info(
      "build",
      `Waiting for integration ${bold(JSON.stringify(name))}, hook ${bold(
        JSON.stringify(hookName)
      )}...`
    );
  }, timeoutMs);
  const result = await hookResult;
  clearTimeout(timeout);
  return result;
}
const Loggers = /* @__PURE__ */ new WeakMap();
function getLogger(integration, logger) {
  if (Loggers.has(integration)) {
    return Loggers.get(integration);
  }
  const integrationLogger = logger.forkIntegrationLogger(integration.name);
  Loggers.set(integration, integrationLogger);
  return integrationLogger;
}
const serverEventPrefix = "astro-dev-toolbar";
function getToolbarServerCommunicationHelpers(server) {
  return {
    /**
     * Send a message to the dev toolbar that an app can listen for. The payload can be any serializable data.
     * @param event - The event name
     * @param payload - The payload to send
     */
    send: (event, payload) => {
      server.hot.send(event, payload);
    },
    /**
     * Receive a message from a dev toolbar app.
     * @param event
     * @param callback
     */
    on: (event, callback) => {
      server.hot.on(event, callback);
    },
    /**
     * Fired when an app is initialized.
     * @param appId - The id of the app that was initialized
     * @param callback - The callback to run when the app is initialized
     */
    onAppInitialized: (appId, callback) => {
      server.hot.on(`${serverEventPrefix}:${appId}:initialized`, callback);
    },
    /**
     * Fired when an app is toggled on or off.
     * @param appId - The id of the app that was toggled
     * @param callback - The callback to run when the app is toggled
     */
    onAppToggled: (appId, callback) => {
      server.hot.on(`${serverEventPrefix}:${appId}:toggled`, callback);
    }
  };
}
const SAFE_CHARS_RE = /[^\w.-]/g;
function normalizeInjectedTypeFilename(filename, integrationName) {
  if (!filename.endsWith(".d.ts")) {
    throw new Error(
      `Integration ${bold(integrationName)} is injecting a type that does not end with "${bold(".d.ts")}"`
    );
  }
  return `./integrations/${integrationName.replace(SAFE_CHARS_RE, "_")}/${filename.replace(SAFE_CHARS_RE, "_")}`;
}
async function runHookConfigSetup({
  settings,
  command,
  logger,
  isRestart = false,
  fs = fsMod
}) {
  if (settings.config.adapter) {
    settings.config.integrations.push(settings.config.adapter);
  }
  if (await isActionsFilePresent(fs, settings.config.srcDir)) {
    settings.config.integrations.push(astroIntegrationActionsRouteHandler({ settings }));
  }
  let updatedConfig = { ...settings.config };
  let updatedSettings = { ...settings, config: updatedConfig };
  let addedClientDirectives = /* @__PURE__ */ new Map();
  let astroJSXRenderer = null;
  for (let i = 0; i < updatedConfig.integrations.length; i++) {
    const integration = updatedConfig.integrations[i];
    if (integration.hooks?.["astro:config:setup"]) {
      let addPageExtension2 = function(...input) {
        const exts = input.flat(Infinity).map((ext) => `.${ext.replace(/^\./, "")}`);
        updatedSettings.pageExtensions.push(...exts);
      }, addContentEntryType2 = function(contentEntryType) {
        updatedSettings.contentEntryTypes.push(contentEntryType);
      }, addDataEntryType2 = function(dataEntryType) {
        updatedSettings.dataEntryTypes.push(dataEntryType);
      };
      var addPageExtension = addPageExtension2, addContentEntryType = addContentEntryType2, addDataEntryType = addDataEntryType2;
      const integrationLogger = getLogger(integration, logger);
      const hooks = {
        config: updatedConfig,
        command,
        isRestart,
        addRenderer(renderer) {
          if (!renderer.name) {
            throw new Error(`Integration ${bold(integration.name)} has an unnamed renderer.`);
          }
          if (!renderer.serverEntrypoint) {
            throw new Error(`Renderer ${bold(renderer.name)} does not provide a serverEntrypoint.`);
          }
          if (renderer.name === "astro:jsx") {
            astroJSXRenderer = renderer;
          } else {
            updatedSettings.renderers.push(renderer);
          }
        },
        injectScript: (stage, content) => {
          updatedSettings.scripts.push({ stage, content });
        },
        updateConfig: (newConfig) => {
          updatedConfig = mergeConfig(updatedConfig, newConfig);
          return { ...updatedConfig };
        },
        injectRoute: (injectRoute) => {
          if (injectRoute.entrypoint == null && "entryPoint" in injectRoute) {
            logger.warn(
              null,
              `The injected route "${injectRoute.pattern}" by ${integration.name} specifies the entry point with the "entryPoint" property. This property is deprecated, please use "entrypoint" instead.`
            );
            injectRoute.entrypoint = injectRoute.entryPoint;
          }
          updatedSettings.injectedRoutes.push(injectRoute);
        },
        addWatchFile: (path) => {
          updatedSettings.watchFiles.push(path instanceof URL ? fileURLToPath(path) : path);
        },
        addDevOverlayPlugin: (entrypoint) => {
          hooks.addDevToolbarApp(entrypoint);
        },
        addDevToolbarApp: (entrypoint) => {
          updatedSettings.devToolbarApps.push(entrypoint);
        },
        addClientDirective: ({ name, entrypoint }) => {
          if (updatedSettings.clientDirectives.has(name) || addedClientDirectives.has(name)) {
            throw new Error(
              `The "${integration.name}" integration is trying to add the "${name}" client directive, but it already exists.`
            );
          }
          addedClientDirectives.set(
            name,
            buildClientDirectiveEntrypoint(name, entrypoint, settings.config.root)
          );
        },
        addMiddleware: ({ order, entrypoint }) => {
          if (typeof updatedSettings.middlewares[order] === "undefined") {
            throw new Error(
              `The "${integration.name}" integration is trying to add middleware but did not specify an order.`
            );
          }
          logger.debug(
            "middleware",
            `The integration ${integration.name} has added middleware that runs ${order === "pre" ? "before" : "after"} any application middleware you define.`
          );
          updatedSettings.middlewares[order].push(entrypoint);
        },
        logger: integrationLogger
      };
      Object.defineProperty(hooks, "addPageExtension", {
        value: addPageExtension2,
        writable: false,
        enumerable: false
      });
      Object.defineProperty(hooks, "addContentEntryType", {
        value: addContentEntryType2,
        writable: false,
        enumerable: false
      });
      Object.defineProperty(hooks, "addDataEntryType", {
        value: addDataEntryType2,
        writable: false,
        enumerable: false
      });
      await withTakingALongTimeMsg({
        name: integration.name,
        hookName: "astro:config:setup",
        hookResult: integration.hooks["astro:config:setup"](hooks),
        logger
      });
      for (const [name, compiled] of addedClientDirectives) {
        updatedSettings.clientDirectives.set(name, await compiled);
      }
    }
  }
  if (astroJSXRenderer) {
    updatedSettings.renderers.push(astroJSXRenderer);
  }
  updatedSettings.config = updatedConfig;
  return updatedSettings;
}
async function runHookConfigDone({
  settings,
  logger
}) {
  for (const integration of settings.config.integrations) {
    if (integration?.hooks?.["astro:config:done"]) {
      await withTakingALongTimeMsg({
        name: integration.name,
        hookName: "astro:config:done",
        hookResult: integration.hooks["astro:config:done"]({
          config: settings.config,
          setAdapter(adapter) {
            if (settings.adapter && settings.adapter.name !== adapter.name) {
              throw new Error(
                `Integration "${integration.name}" conflicts with "${settings.adapter.name}". You can only configure one deployment integration.`
              );
            }
            if (!adapter.supportedAstroFeatures) {
              throw new Error(
                `The adapter ${adapter.name} doesn't provide a feature map. It is required in Astro 4.0.`
              );
            } else {
              const validationResult = validateSupportedFeatures(
                adapter.name,
                adapter.supportedAstroFeatures,
                settings.config,
                // SAFETY: we checked before if it's not present, and we throw an error
                adapter.adapterFeatures,
                logger
              );
              for (const [featureName, supported] of Object.entries(validationResult)) {
                if (!supported && featureName !== "assets") {
                  logger.error(
                    null,
                    `The adapter ${adapter.name} doesn't support the feature ${featureName}. Your project won't be built. You should not use it.`
                  );
                }
              }
            }
            settings.adapter = adapter;
          },
          injectTypes(injectedType) {
            const normalizedFilename = normalizeInjectedTypeFilename(
              injectedType.filename,
              integration.name
            );
            settings.injectedTypes.push({
              filename: normalizedFilename,
              content: injectedType.content
            });
            return new URL(normalizedFilename, settings.dotAstroDir);
          },
          logger: getLogger(integration, logger)
        }),
        logger
      });
    }
  }
}
async function runHookServerSetup({
  config,
  server,
  logger
}) {
  for (const integration of config.integrations) {
    if (integration?.hooks?.["astro:server:setup"]) {
      await withTakingALongTimeMsg({
        name: integration.name,
        hookName: "astro:server:setup",
        hookResult: integration.hooks["astro:server:setup"]({
          server,
          logger: getLogger(integration, logger),
          toolbar: getToolbarServerCommunicationHelpers(server)
        }),
        logger
      });
    }
  }
}
async function runHookServerStart({
  config,
  address,
  logger
}) {
  for (const integration of config.integrations) {
    if (integration?.hooks?.["astro:server:start"]) {
      await withTakingALongTimeMsg({
        name: integration.name,
        hookName: "astro:server:start",
        hookResult: integration.hooks["astro:server:start"]({
          address,
          logger: getLogger(integration, logger)
        }),
        logger
      });
    }
  }
}
async function runHookServerDone({
  config,
  logger
}) {
  for (const integration of config.integrations) {
    if (integration?.hooks?.["astro:server:done"]) {
      await withTakingALongTimeMsg({
        name: integration.name,
        hookName: "astro:server:done",
        hookResult: integration.hooks["astro:server:done"]({
          logger: getLogger(integration, logger)
        }),
        logger
      });
    }
  }
}
async function runHookBuildStart({
  config,
  logging
}) {
  for (const integration of config.integrations) {
    if (integration?.hooks?.["astro:build:start"]) {
      const logger = getLogger(integration, logging);
      await withTakingALongTimeMsg({
        name: integration.name,
        hookName: "astro:build:start",
        hookResult: integration.hooks["astro:build:start"]({ logger }),
        logger: logging
      });
    }
  }
}
async function runHookBuildSetup({
  config,
  vite,
  pages,
  target,
  logger
}) {
  let updatedConfig = vite;
  for (const integration of config.integrations) {
    if (integration?.hooks?.["astro:build:setup"]) {
      await withTakingALongTimeMsg({
        name: integration.name,
        hookName: "astro:build:setup",
        hookResult: integration.hooks["astro:build:setup"]({
          vite,
          pages,
          target,
          updateConfig: (newConfig) => {
            updatedConfig = mergeConfig(updatedConfig, newConfig);
            return { ...updatedConfig };
          },
          logger: getLogger(integration, logger)
        }),
        logger
      });
    }
  }
  return updatedConfig;
}
async function runHookBuildSsr({
  config,
  manifest,
  logger,
  entryPoints,
  middlewareEntryPoint
}) {
  for (const integration of config.integrations) {
    if (integration?.hooks?.["astro:build:ssr"]) {
      await withTakingALongTimeMsg({
        name: integration.name,
        hookName: "astro:build:ssr",
        hookResult: integration.hooks["astro:build:ssr"]({
          manifest,
          entryPoints,
          middlewareEntryPoint,
          logger: getLogger(integration, logger)
        }),
        logger
      });
    }
  }
}
async function runHookBuildGenerated({
  config,
  logger
}) {
  const dir = isServerLikeOutput(config) ? config.build.client : config.outDir;
  for (const integration of config.integrations) {
    if (integration?.hooks?.["astro:build:generated"]) {
      await withTakingALongTimeMsg({
        name: integration.name,
        hookName: "astro:build:generated",
        hookResult: integration.hooks["astro:build:generated"]({
          dir,
          logger: getLogger(integration, logger)
        }),
        logger
      });
    }
  }
}
async function runHookBuildDone({
  config,
  pages,
  routes,
  logging,
  cacheManifest
}) {
  const dir = isServerLikeOutput(config) ? config.build.client : config.outDir;
  await fsMod.promises.mkdir(dir, { recursive: true });
  for (const integration of config.integrations) {
    if (integration?.hooks?.["astro:build:done"]) {
      const logger = getLogger(integration, logging);
      await withTakingALongTimeMsg({
        name: integration.name,
        hookName: "astro:build:done",
        hookResult: integration.hooks["astro:build:done"]({
          pages: pages.map((p) => ({ pathname: p })),
          dir,
          routes,
          logger,
          cacheManifest
        }),
        logger: logging
      });
    }
  }
}
async function runHookRouteSetup({
  route,
  settings,
  logger
}) {
  const prerenderChangeLogs = [];
  for (const integration of settings.config.integrations) {
    if (integration?.hooks?.["astro:route:setup"]) {
      const originalRoute = { ...route };
      const integrationLogger = getLogger(integration, logger);
      await withTakingALongTimeMsg({
        name: integration.name,
        hookName: "astro:route:setup",
        hookResult: integration.hooks["astro:route:setup"]({
          route,
          logger: integrationLogger
        }),
        logger
      });
      if (route.prerender !== originalRoute.prerender) {
        prerenderChangeLogs.push({ integrationName: integration.name, value: route.prerender });
      }
    }
  }
  if (prerenderChangeLogs.length > 1) {
    logger.debug(
      "router",
      `The ${route.component} route's prerender option has been changed multiple times by integrations:
` + prerenderChangeLogs.map((log) => `- ${log.integrationName}: ${log.value}`).join("\n")
    );
  }
}
function isFunctionPerRouteEnabled(adapter) {
  if (adapter?.adapterFeatures?.functionPerRoute === true) {
    return true;
  } else {
    return false;
  }
}
export {
  getToolbarServerCommunicationHelpers,
  isFunctionPerRouteEnabled,
  normalizeInjectedTypeFilename,
  runHookBuildDone,
  runHookBuildGenerated,
  runHookBuildSetup,
  runHookBuildSsr,
  runHookBuildStart,
  runHookConfigDone,
  runHookConfigSetup,
  runHookRouteSetup,
  runHookServerDone,
  runHookServerSetup,
  runHookServerStart
};
