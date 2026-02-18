import { PROPAGATED_ASSET_FLAG } from "../../../content/consts.js";
import { prependForwardSlash } from "../../../core/path.js";
import {
  getParentModuleInfos,
  getTopLevelPageModuleInfos,
  moduleIsTopLevelPage
} from "../graph.js";
import {
  getPageDataByViteID,
  trackClientOnlyPageDatas,
  trackScriptPageDatas
} from "../internal.js";
function isPropagatedAsset(id) {
  try {
    return new URL("file://" + id).searchParams.has(PROPAGATED_ASSET_FLAG);
  } catch {
    return false;
  }
}
function vitePluginAnalyzer(options, internals) {
  function hoistedScriptScanner() {
    const uniqueHoistedIds = /* @__PURE__ */ new Map();
    const pageScriptsMap = /* @__PURE__ */ new Map();
    return {
      async scan(scripts, from) {
        const hoistedScripts = /* @__PURE__ */ new Set();
        for (let i = 0; i < scripts.length; i++) {
          const hid = `${from.replace("/@fs", "")}?astro&type=script&index=${i}&lang.ts`;
          hoistedScripts.add(hid);
        }
        if (hoistedScripts.size) {
          for (const parentInfo of getParentModuleInfos(from, this, isPropagatedAsset)) {
            if (isPropagatedAsset(parentInfo.id)) {
              if (!internals.propagatedScriptsMap.has(parentInfo.id)) {
                internals.propagatedScriptsMap.set(parentInfo.id, /* @__PURE__ */ new Set());
              }
              const propagatedScripts = internals.propagatedScriptsMap.get(parentInfo.id);
              for (const hid of hoistedScripts) {
                propagatedScripts.add(hid);
              }
            } else if (moduleIsTopLevelPage(parentInfo)) {
              if (!pageScriptsMap.has(parentInfo.id)) {
                pageScriptsMap.set(parentInfo.id, {
                  hoistedSet: /* @__PURE__ */ new Set()
                });
              }
              const pageScripts = pageScriptsMap.get(parentInfo.id);
              for (const hid of hoistedScripts) {
                pageScripts.hoistedSet.add(hid);
              }
            }
          }
        }
      },
      finalize() {
        for (const propagatedScripts of internals.propagatedScriptsMap.values()) {
          for (const propagatedScript of propagatedScripts) {
            internals.discoveredScripts.add(propagatedScript);
          }
        }
        for (const [pageId, { hoistedSet }] of pageScriptsMap) {
          const pageData = getPageDataByViteID(internals, pageId);
          if (!pageData) continue;
          const { component } = pageData;
          const astroModuleId = prependForwardSlash(component);
          const uniqueHoistedId = JSON.stringify(Array.from(hoistedSet).sort());
          let moduleId;
          if (uniqueHoistedIds.has(uniqueHoistedId)) {
            moduleId = uniqueHoistedIds.get(uniqueHoistedId);
          } else {
            moduleId = `/astro/hoisted.js?q=${uniqueHoistedIds.size}`;
            uniqueHoistedIds.set(uniqueHoistedId, moduleId);
          }
          internals.discoveredScripts.add(moduleId);
          if (internals.hoistedScriptIdToPagesMap.has(moduleId)) {
            const pages = internals.hoistedScriptIdToPagesMap.get(moduleId);
            pages.add(astroModuleId);
          } else {
            internals.hoistedScriptIdToPagesMap.set(moduleId, /* @__PURE__ */ new Set([astroModuleId]));
            internals.hoistedScriptIdToHoistedMap.set(moduleId, hoistedSet);
          }
        }
      }
    };
  }
  return {
    name: "@astro/rollup-plugin-astro-analyzer",
    async generateBundle() {
      const hoistScanner = options.settings.config.experimental.directRenderScript ? { scan: async () => {
      }, finalize: () => {
      } } : hoistedScriptScanner();
      const ids = this.getModuleIds();
      for (const id of ids) {
        const info = this.getModuleInfo(id);
        if (!info?.meta?.astro) continue;
        const astro = info.meta.astro;
        for (const c of astro.hydratedComponents) {
          const rid = c.resolvedPath ? decodeURI(c.resolvedPath) : c.specifier;
          if (internals.discoveredHydratedComponents.has(rid)) {
            const exportNames = internals.discoveredHydratedComponents.get(rid);
            exportNames?.push(c.exportName);
          } else {
            internals.discoveredHydratedComponents.set(rid, [c.exportName]);
          }
        }
        await hoistScanner.scan.call(this, astro.scripts, id);
        if (astro.clientOnlyComponents.length) {
          const clientOnlys = [];
          for (const c of astro.clientOnlyComponents) {
            const cid = c.resolvedPath ? decodeURI(c.resolvedPath) : c.specifier;
            if (internals.discoveredClientOnlyComponents.has(cid)) {
              const exportNames = internals.discoveredClientOnlyComponents.get(cid);
              exportNames?.push(c.exportName);
            } else {
              internals.discoveredClientOnlyComponents.set(cid, [c.exportName]);
            }
            clientOnlys.push(cid);
            const resolvedId = await this.resolve(c.specifier, id);
            if (resolvedId) {
              clientOnlys.push(resolvedId.id);
            }
          }
          for (const pageInfo of getTopLevelPageModuleInfos(id, this)) {
            const newPageData = getPageDataByViteID(internals, pageInfo.id);
            if (!newPageData) continue;
            trackClientOnlyPageDatas(internals, newPageData, clientOnlys);
          }
        }
        if (options.settings.config.experimental.directRenderScript && astro.scripts.length) {
          const scriptIds = astro.scripts.map(
            (_, i) => `${id.replace("/@fs", "")}?astro&type=script&index=${i}&lang.ts`
          );
          for (const scriptId of scriptIds) {
            internals.discoveredScripts.add(scriptId);
          }
          for (const pageInfo of getTopLevelPageModuleInfos(id, this)) {
            const newPageData = getPageDataByViteID(internals, pageInfo.id);
            if (!newPageData) continue;
            trackScriptPageDatas(internals, newPageData, scriptIds);
          }
        }
      }
      hoistScanner.finalize();
    }
  };
}
function pluginAnalyzer(options, internals) {
  return {
    targets: ["server"],
    hooks: {
      "build:before": () => {
        return {
          vitePlugin: vitePluginAnalyzer(options, internals)
        };
      }
    }
  };
}
export {
  pluginAnalyzer,
  vitePluginAnalyzer
};
