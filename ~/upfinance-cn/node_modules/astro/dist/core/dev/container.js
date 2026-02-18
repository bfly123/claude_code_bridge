import nodeFs from "node:fs";
import * as vite from "vite";
import { injectImageEndpoint } from "../../assets/endpoint/config.js";
import {
  runHookConfigDone,
  runHookConfigSetup,
  runHookServerDone,
  runHookServerStart
} from "../../integrations/hooks.js";
import { createVite } from "../create-vite.js";
import { apply as applyPolyfill } from "../polyfill.js";
import { syncInternal } from "../sync/index.js";
async function createContainer({
  isRestart = false,
  logger,
  inlineConfig,
  settings,
  fs = nodeFs
}) {
  applyPolyfill();
  settings = await runHookConfigSetup({
    settings,
    command: "dev",
    logger,
    isRestart
  });
  settings = injectImageEndpoint(settings, "dev");
  const {
    base,
    server: { host, headers, open: serverOpen }
  } = settings.config;
  const isServerOpenURL = typeof serverOpen == "string" && !isRestart;
  const isServerOpenBoolean = serverOpen && !isRestart;
  const open = isServerOpenURL ? serverOpen : isServerOpenBoolean ? base : false;
  const rendererClientEntries = settings.renderers.map((r) => r.clientEntrypoint).filter(Boolean);
  const viteConfig = await createVite(
    {
      mode: "development",
      server: { host, headers, open },
      optimizeDeps: {
        include: rendererClientEntries
      }
    },
    { settings, logger, mode: "dev", command: "dev", fs, sync: false }
  );
  await runHookConfigDone({ settings, logger });
  await syncInternal({
    settings,
    logger,
    skip: {
      content: true
    },
    force: inlineConfig?.force
  });
  const viteServer = await vite.createServer(viteConfig);
  const container = {
    inlineConfig: inlineConfig ?? {},
    fs,
    logger,
    restartInFlight: false,
    settings,
    viteServer,
    handle(req, res) {
      viteServer.middlewares.handle(req, res, Function.prototype);
    },
    // TODO deprecate and remove
    close() {
      return closeContainer(container);
    }
  };
  return container;
}
async function closeContainer({ viteServer, settings, logger }) {
  await viteServer.close();
  await runHookServerDone({
    config: settings.config,
    logger
  });
}
async function startContainer({
  settings,
  viteServer,
  logger
}) {
  const { port } = settings.config.server;
  await viteServer.listen(port);
  const devServerAddressInfo = viteServer.httpServer.address();
  await runHookServerStart({
    config: settings.config,
    address: devServerAddressInfo,
    logger
  });
  return devServerAddressInfo;
}
export {
  createContainer,
  startContainer
};
