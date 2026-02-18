import { jsxTransformOptions } from "./transform-options.js";
const renderer = {
  name: "astro:jsx",
  serverEntrypoint: "astro/jsx/server.js",
  jsxImportSource: "astro",
  jsxTransformOptions
};
var renderer_default = renderer;
export {
  renderer_default as default
};
