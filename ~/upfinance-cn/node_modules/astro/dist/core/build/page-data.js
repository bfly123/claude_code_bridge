import * as colors from "kleur/colors";
import { debug } from "../logger/core.js";
import { makePageDataKey } from "./plugins/util.js";
function collectPagesData(opts) {
  const { settings, manifest } = opts;
  const assets = {};
  const allPages = {};
  for (const route of manifest.routes) {
    const key = makePageDataKey(route.route, route.component);
    if (route.pathname) {
      allPages[key] = {
        key,
        component: route.component,
        route,
        moduleSpecifier: "",
        styles: [],
        hoistedScript: void 0
      };
      if (settings.config.output === "static") {
        const html = `${route.pathname}`.replace(/\/?$/, "/index.html");
        debug(
          "build",
          `\u251C\u2500\u2500 ${colors.bold(colors.green("\u2714"))} ${route.component} \u2192 ${colors.yellow(html)}`
        );
      } else {
        debug("build", `\u251C\u2500\u2500 ${colors.bold(colors.green("\u2714"))} ${route.component}`);
      }
      continue;
    }
    allPages[key] = {
      key,
      component: route.component,
      route,
      moduleSpecifier: "",
      styles: [],
      hoistedScript: void 0
    };
  }
  return { assets, allPages };
}
export {
  collectPagesData
};
