import { getOutDirWithinCwd } from "../core/build/common.js";
import { isServerLikeOutput } from "../core/util.js";
function getPrerenderDefault(config) {
  return config.output !== "server";
}
function getOutputDirectory(config) {
  const ssr = isServerLikeOutput(config);
  if (ssr) {
    return config.build.server;
  } else {
    return getOutDirWithinCwd(config.outDir);
  }
}
export {
  getOutputDirectory,
  getPrerenderDefault
};
