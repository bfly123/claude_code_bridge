import * as eslexer from "es-module-lexer";
import { ACTION_API_CONTEXT_SYMBOL } from "./runtime/utils.js";
import { deserializeActionResult, getActionQueryString } from "./runtime/virtual/shared.js";
function hasActionPayload(locals) {
  return "_actionPayload" in locals;
}
function createGetActionResult(locals) {
  return (actionFn) => {
    if (!hasActionPayload(locals) || actionFn.toString() !== getActionQueryString(locals._actionPayload.actionName)) {
      return void 0;
    }
    return deserializeActionResult(locals._actionPayload.actionResult);
  };
}
function createCallAction(context) {
  return (baseAction, input) => {
    Reflect.set(context, ACTION_API_CONTEXT_SYMBOL, true);
    const action = baseAction.bind(context);
    return action(input);
  };
}
let didInitLexer = false;
async function isActionsFilePresent(fs, srcDir) {
  if (!didInitLexer) await eslexer.init;
  const actionsFile = search(fs, srcDir);
  if (!actionsFile) return false;
  let contents;
  try {
    contents = fs.readFileSync(actionsFile, "utf-8");
  } catch {
    return false;
  }
  const [, exports] = eslexer.parse(contents, actionsFile.pathname);
  for (const exp of exports) {
    if (exp.n === "server") {
      return true;
    }
  }
  return false;
}
function search(fs, srcDir) {
  const paths = [
    "actions.mjs",
    "actions.js",
    "actions.mts",
    "actions.ts",
    "actions/index.mjs",
    "actions/index.js",
    "actions/index.mts",
    "actions/index.ts"
  ].map((p) => new URL(p, srcDir));
  for (const file of paths) {
    if (fs.existsSync(file)) {
      return file;
    }
  }
  return void 0;
}
export {
  createCallAction,
  createGetActionResult,
  hasActionPayload,
  isActionsFilePresent
};
