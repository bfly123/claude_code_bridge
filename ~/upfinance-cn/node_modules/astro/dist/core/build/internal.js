import { prependForwardSlash, removeFileExtension } from "../path.js";
import { viteID } from "../util.js";
import { makePageDataKey } from "./plugins/util.js";
function createBuildInternals() {
  const hoistedScriptIdToHoistedMap = /* @__PURE__ */ new Map();
  const hoistedScriptIdToPagesMap = /* @__PURE__ */ new Map();
  return {
    cachedClientEntries: [],
    cssModuleToChunkIdMap: /* @__PURE__ */ new Map(),
    hoistedScriptIdToHoistedMap,
    hoistedScriptIdToPagesMap,
    inlinedScripts: /* @__PURE__ */ new Map(),
    entrySpecifierToBundleMap: /* @__PURE__ */ new Map(),
    pagesByKeys: /* @__PURE__ */ new Map(),
    pagesByViteID: /* @__PURE__ */ new Map(),
    pagesByClientOnly: /* @__PURE__ */ new Map(),
    pagesByScriptId: /* @__PURE__ */ new Map(),
    propagatedStylesMap: /* @__PURE__ */ new Map(),
    propagatedScriptsMap: /* @__PURE__ */ new Map(),
    discoveredHydratedComponents: /* @__PURE__ */ new Map(),
    discoveredClientOnlyComponents: /* @__PURE__ */ new Map(),
    discoveredScripts: /* @__PURE__ */ new Set(),
    staticFiles: /* @__PURE__ */ new Set(),
    componentMetadata: /* @__PURE__ */ new Map(),
    entryPoints: /* @__PURE__ */ new Map(),
    cacheManifestUsed: false,
    prerenderOnlyChunks: []
  };
}
function trackPageData(internals, _component, pageData, componentModuleId, componentURL) {
  pageData.moduleSpecifier = componentModuleId;
  internals.pagesByKeys.set(pageData.key, pageData);
  internals.pagesByViteID.set(viteID(componentURL), pageData);
}
function trackClientOnlyPageDatas(internals, pageData, clientOnlys) {
  for (const clientOnlyComponent of clientOnlys) {
    let pageDataSet;
    if (internals.pagesByClientOnly.has(clientOnlyComponent)) {
      pageDataSet = internals.pagesByClientOnly.get(clientOnlyComponent);
    } else {
      pageDataSet = /* @__PURE__ */ new Set();
      internals.pagesByClientOnly.set(clientOnlyComponent, pageDataSet);
    }
    pageDataSet.add(pageData);
  }
}
function trackScriptPageDatas(internals, pageData, scriptIds) {
  for (const scriptId of scriptIds) {
    let pageDataSet;
    if (internals.pagesByScriptId.has(scriptId)) {
      pageDataSet = internals.pagesByScriptId.get(scriptId);
    } else {
      pageDataSet = /* @__PURE__ */ new Set();
      internals.pagesByScriptId.set(scriptId, pageDataSet);
    }
    pageDataSet.add(pageData);
  }
}
function* getPageDatasByClientOnlyID(internals, viteid) {
  const pagesByClientOnly = internals.pagesByClientOnly;
  if (pagesByClientOnly.size) {
    let pageBuildDatas = pagesByClientOnly.get(viteid);
    if (!pageBuildDatas) {
      let pathname = `/@fs${prependForwardSlash(viteid)}`;
      pageBuildDatas = pagesByClientOnly.get(pathname);
    }
    if (!pageBuildDatas) {
      let pathname = `/@fs${prependForwardSlash(removeFileExtension(viteid))}`;
      pageBuildDatas = pagesByClientOnly.get(pathname);
    }
    if (pageBuildDatas) {
      for (const pageData of pageBuildDatas) {
        yield pageData;
      }
    }
  }
}
function getPageData(internals, route, component) {
  let pageData = internals.pagesByKeys.get(makePageDataKey(route, component));
  if (pageData) {
    return pageData;
  }
  return void 0;
}
function getPagesDatasByComponent(internals, component) {
  const pageDatas = [];
  internals.pagesByKeys.forEach((pageData) => {
    if (component === pageData.component) pageDatas.push(pageData);
  });
  return pageDatas;
}
function getPageDatasWithPublicKey(pagesByKeys) {
  const pagesWithPublicKey = /* @__PURE__ */ new Map();
  const pagesByComponentsArray = Array.from(pagesByKeys.values()).map((pageData) => {
    return { component: pageData.component, pageData };
  });
  const pagesWithUniqueComponent = pagesByComponentsArray.filter((page) => {
    return pagesByComponentsArray.filter((p) => p.component === page.component).length === 1;
  });
  pagesWithUniqueComponent.forEach((page) => {
    pagesWithPublicKey.set(page.component, page.pageData);
  });
  const pagesWithSharedComponent = pagesByComponentsArray.filter((page) => {
    return pagesByComponentsArray.filter((p) => p.component === page.component).length > 1;
  });
  pagesWithSharedComponent.forEach((page) => {
    pagesWithPublicKey.set(page.pageData.key, page.pageData);
  });
  return pagesWithPublicKey;
}
function getPageDataByViteID(internals, viteid) {
  if (internals.pagesByViteID.has(viteid)) {
    return internals.pagesByViteID.get(viteid);
  }
  return void 0;
}
function hasPrerenderedPages(internals) {
  for (const pageData of internals.pagesByKeys.values()) {
    if (pageData.route.prerender) {
      return true;
    }
  }
  return false;
}
function cssOrder(a, b) {
  let depthA = a.depth, depthB = b.depth, orderA = a.order, orderB = b.order;
  if (orderA === -1 && orderB >= 0) {
    return 1;
  } else if (orderB === -1 && orderA >= 0) {
    return -1;
  } else if (orderA > orderB) {
    return 1;
  } else if (orderA < orderB) {
    return -1;
  } else {
    if (depthA === -1) {
      return -1;
    } else if (depthB === -1) {
      return 1;
    } else {
      return depthA > depthB ? -1 : 1;
    }
  }
}
function mergeInlineCss(acc, current) {
  const lastAdded = acc.at(acc.length - 1);
  const lastWasInline = lastAdded?.type === "inline";
  const currentIsInline = current?.type === "inline";
  if (lastWasInline && currentIsInline) {
    const merged = { type: "inline", content: lastAdded.content + current.content };
    acc[acc.length - 1] = merged;
    return acc;
  }
  acc.push(current);
  return acc;
}
function getPageDatasByHoistedScriptId(internals, id) {
  const set = internals.hoistedScriptIdToPagesMap.get(id);
  const pageDatas = [];
  if (set) {
    for (const pageId of set) {
      getPagesDatasByComponent(internals, pageId.slice(1)).forEach((pageData) => {
        pageDatas.push(pageData);
      });
    }
  }
  return pageDatas;
}
export {
  createBuildInternals,
  cssOrder,
  getPageData,
  getPageDataByViteID,
  getPageDatasByClientOnlyID,
  getPageDatasByHoistedScriptId,
  getPageDatasWithPublicKey,
  hasPrerenderedPages,
  mergeInlineCss,
  trackClientOnlyPageDatas,
  trackPageData,
  trackScriptPageDatas
};
