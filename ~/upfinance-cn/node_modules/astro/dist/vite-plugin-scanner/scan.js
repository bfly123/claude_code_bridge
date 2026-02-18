import * as eslexer from "es-module-lexer";
import { AstroError, AstroErrorData } from "../core/errors/index.js";
const BOOLEAN_EXPORTS = /* @__PURE__ */ new Set(["prerender"]);
function includesExport(code) {
  for (const name of BOOLEAN_EXPORTS) {
    if (code.includes(name)) return true;
  }
  return false;
}
function isQuoted(value) {
  return (value[0] === '"' || value[0] === "'") && value[value.length - 1] === value[0];
}
function isTruthy(value) {
  if (isQuoted(value)) {
    value = value.slice(1, -1);
  }
  return value === "true" || value === "1";
}
function isFalsy(value) {
  if (isQuoted(value)) {
    value = value.slice(1, -1);
  }
  return value === "false" || value === "0";
}
let didInit = false;
async function scan(code, id, settings) {
  if (!includesExport(code)) return {};
  if (!didInit) {
    await eslexer.init;
    didInit = true;
  }
  const [, exports] = eslexer.parse(code, id);
  let pageOptions = {};
  for (const _export of exports) {
    const { n: name, le: endOfLocalName } = _export;
    if (BOOLEAN_EXPORTS.has(name)) {
      const prefix = code.slice(0, endOfLocalName).split("export").pop().trim().replace("prerender", "").trim();
      const suffix = code.slice(endOfLocalName).trim().replace(/=/, "").trim().split(/[;\n\r]/)[0].trim();
      if (prefix !== "const" || !(isTruthy(suffix) || isFalsy(suffix))) {
        throw new AstroError({
          ...AstroErrorData.InvalidPrerenderExport,
          message: AstroErrorData.InvalidPrerenderExport.message(
            prefix,
            suffix,
            settings?.config.output === "hybrid"
          ),
          location: { file: id }
        });
      } else {
        pageOptions[name] = isTruthy(suffix);
      }
    }
  }
  return pageOptions;
}
export {
  scan
};
