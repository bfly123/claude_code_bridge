import babel from "@babel/core";
import { jsxTransformOptions } from "../jsx/transform-options.js";
import { tagExportsPlugin } from "./tag.js";
async function transformJSX(code, id, ssr) {
  const options = await getJsxTransformOptions();
  const plugins = ssr ? [...options.plugins ?? [], tagExportsPlugin] : options.plugins;
  const result = await babel.transformAsync(code, {
    presets: options.presets,
    plugins,
    cwd: process.cwd(),
    filename: id,
    ast: false,
    compact: false,
    sourceMaps: true,
    configFile: false,
    babelrc: false,
    browserslistConfigFile: false,
    inputSourceMap: options.inputSourceMap
  });
  if (!result) return null;
  const { astro } = result.metadata;
  return {
    code: result.code || "",
    map: result.map,
    meta: {
      astro,
      vite: {
        // Setting this vite metadata to `ts` causes Vite to resolve .js
        // extensions to .ts files.
        lang: "ts"
      }
    }
  };
}
let cachedJsxTransformOptions;
async function getJsxTransformOptions() {
  if (cachedJsxTransformOptions) {
    return cachedJsxTransformOptions;
  }
  const options = jsxTransformOptions();
  cachedJsxTransformOptions = options;
  options.then((resolvedOptions) => {
    cachedJsxTransformOptions = resolvedOptions;
  });
  return options;
}
export {
  transformJSX
};
