import { definitions } from "mdast-util-definitions";
import { visit } from "unist-util-visit";
function remarkCollectImages() {
  return function(tree, vfile) {
    if (typeof vfile?.path !== "string") return;
    const definition = definitions(tree);
    const imagePaths = /* @__PURE__ */ new Set();
    visit(tree, ["image", "imageReference"], (node) => {
      if (node.type === "image") {
        if (shouldOptimizeImage(node.url)) imagePaths.add(decodeURI(node.url));
      }
      if (node.type === "imageReference") {
        const imageDefinition = definition(node.identifier);
        if (imageDefinition) {
          if (shouldOptimizeImage(imageDefinition.url))
            imagePaths.add(decodeURI(imageDefinition.url));
        }
      }
    });
    vfile.data.imagePaths = imagePaths;
  };
}
function shouldOptimizeImage(src) {
  return !isValidUrl(src) && !src.startsWith("/");
}
function isValidUrl(str) {
  try {
    new URL(str);
    return true;
  } catch {
    return false;
  }
}
export {
  remarkCollectImages
};
