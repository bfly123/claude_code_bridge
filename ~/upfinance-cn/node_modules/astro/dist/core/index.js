import { default as _build } from "./build/index.js";
import { default as _sync } from "./sync/index.js";
import { default as default2 } from "./dev/index.js";
import { default as default3 } from "./preview/index.js";
const build = (inlineConfig) => _build(inlineConfig);
const sync = (inlineConfig) => _sync(inlineConfig);
export {
  build,
  default2 as dev,
  default3 as preview,
  sync
};
