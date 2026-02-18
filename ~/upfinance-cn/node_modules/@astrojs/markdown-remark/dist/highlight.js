import { fromHtml } from "hast-util-from-html";
import { toText } from "hast-util-to-text";
import { removePosition } from "unist-util-remove-position";
import { visitParents } from "unist-util-visit-parents";
const languagePattern = /\blanguage-(\S+)\b/;
async function highlightCodeBlocks(tree, highlighter) {
  const nodes = [];
  visitParents(tree, { type: "element", tagName: "code" }, (node, ancestors) => {
    const parent = ancestors.at(-1);
    if (parent?.type !== "element" || parent.tagName !== "pre") {
      return;
    }
    if (parent.children.length !== 1) {
      return;
    }
    let languageMatch;
    let { className } = node.properties;
    if (typeof className === "string") {
      languageMatch = languagePattern.exec(className);
    } else if (Array.isArray(className)) {
      for (const cls of className) {
        if (typeof cls !== "string") {
          continue;
        }
        languageMatch = languagePattern.exec(cls);
        if (languageMatch) {
          break;
        }
      }
    }
    if (languageMatch?.[1] === "math") {
      return;
    }
    nodes.push({
      node,
      language: languageMatch?.[1] || "plaintext",
      parent,
      grandParent: ancestors.at(-2)
    });
  });
  for (const { node, language, grandParent, parent } of nodes) {
    const meta = node.data?.meta ?? node.properties.metastring ?? void 0;
    const code = toText(node, { whitespace: "pre" });
    const html = await highlighter(code, language, { meta });
    const replacement = fromHtml(html, { fragment: true }).children[0];
    removePosition(replacement);
    const index = grandParent.children.indexOf(parent);
    grandParent.children[index] = replacement;
  }
}
export {
  highlightCodeBlocks
};
