import islandScriptDev from "./astro-island.prebuilt-dev.js";
import islandScript from "./astro-island.prebuilt.js";
const ISLAND_STYLES = `<style>astro-island,astro-slot,astro-static-slot{display:contents}</style>`;
function determineIfNeedsHydrationScript(result) {
  if (result._metadata.hasHydrationScript) {
    return false;
  }
  return result._metadata.hasHydrationScript = true;
}
function determinesIfNeedsDirectiveScript(result, directive) {
  if (result._metadata.hasDirectives.has(directive)) {
    return false;
  }
  result._metadata.hasDirectives.add(directive);
  return true;
}
function getDirectiveScriptText(result, directive) {
  const clientDirectives = result.clientDirectives;
  const clientDirective = clientDirectives.get(directive);
  if (!clientDirective) {
    throw new Error(`Unknown directive: ${directive}`);
  }
  return clientDirective;
}
function getPrescripts(result, type, directive) {
  switch (type) {
    case "both":
      return `${ISLAND_STYLES}<script>${getDirectiveScriptText(result, directive)};${process.env.NODE_ENV === "development" ? islandScriptDev : islandScript}</script>`;
    case "directive":
      return `<script>${getDirectiveScriptText(result, directive)}</script>`;
    case null:
      break;
  }
  return "";
}
export {
  determineIfNeedsHydrationScript,
  determinesIfNeedsDirectiveScript,
  getPrescripts
};
