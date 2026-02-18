import { visit } from "unist-util-visit";
function rehypeImages() {
  return () => function(tree, file) {
    const imageOccurrenceMap = /* @__PURE__ */ new Map();
    visit(tree, (node) => {
      if (node.type !== "element") return;
      if (node.tagName !== "img") return;
      if (node.properties?.src) {
        node.properties.src = decodeURI(node.properties.src);
        if (file.data.imagePaths?.has(node.properties.src)) {
          const { ...props } = node.properties;
          const index = imageOccurrenceMap.get(node.properties.src) || 0;
          imageOccurrenceMap.set(node.properties.src, index + 1);
          node.properties["__ASTRO_IMAGE_"] = JSON.stringify({ ...props, index });
          Object.keys(props).forEach((prop) => {
            delete node.properties[prop];
          });
        }
      }
    });
  };
}
export {
  rehypeImages
};
