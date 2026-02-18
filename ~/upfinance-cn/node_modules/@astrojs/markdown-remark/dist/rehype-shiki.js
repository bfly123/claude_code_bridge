import { highlightCodeBlocks } from "./highlight.js";
import { createShikiHighlighter } from "./shiki.js";
const rehypeShiki = (config) => {
  let highlighterAsync;
  return async (tree) => {
    highlighterAsync ??= createShikiHighlighter(config);
    const highlighter = await highlighterAsync;
    await highlightCodeBlocks(tree, highlighter.highlight);
  };
};
export {
  rehypeShiki
};
