import * as t from "@babel/types";
import { AstroError } from "../core/errors/errors.js";
import { AstroErrorData } from "../core/errors/index.js";
import { resolvePath } from "../core/viteUtils.js";
import { createDefaultAstroMetadata } from "../vite-plugin-astro/metadata.js";
const ClientOnlyPlaceholder = "astro-client-only";
function isComponent(tagName) {
  return tagName[0] && tagName[0].toLowerCase() !== tagName[0] || tagName.includes(".") || /[^a-zA-Z]/.test(tagName[0]);
}
function hasClientDirective(node) {
  for (const attr of node.openingElement.attributes) {
    if (attr.type === "JSXAttribute" && attr.name.type === "JSXNamespacedName") {
      return attr.name.namespace.name === "client";
    }
  }
  return false;
}
function isClientOnlyComponent(node) {
  for (const attr of node.openingElement.attributes) {
    if (attr.type === "JSXAttribute" && attr.name.type === "JSXNamespacedName") {
      return jsxAttributeToString(attr) === "client:only";
    }
  }
  return false;
}
function getTagName(tag) {
  const jsxName = tag.openingElement.name;
  return jsxElementNameToString(jsxName);
}
function jsxElementNameToString(node) {
  if (t.isJSXMemberExpression(node)) {
    return `${jsxElementNameToString(node.object)}.${node.property.name}`;
  }
  if (t.isJSXIdentifier(node) || t.isIdentifier(node)) {
    return node.name;
  }
  return `${node.namespace.name}:${node.name.name}`;
}
function jsxAttributeToString(attr) {
  if (t.isJSXNamespacedName(attr.name)) {
    return `${attr.name.namespace.name}:${attr.name.name.name}`;
  }
  return `${attr.name.name}`;
}
function addClientMetadata(node, meta) {
  const existingAttributes = node.openingElement.attributes.map(
    (attr) => t.isJSXAttribute(attr) ? jsxAttributeToString(attr) : null
  );
  if (!existingAttributes.find((attr) => attr === "client:component-path")) {
    const componentPath = t.jsxAttribute(
      t.jsxNamespacedName(t.jsxIdentifier("client"), t.jsxIdentifier("component-path")),
      t.stringLiteral(meta.resolvedPath)
    );
    node.openingElement.attributes.push(componentPath);
  }
  if (!existingAttributes.find((attr) => attr === "client:component-export")) {
    if (meta.name === "*") {
      meta.name = getTagName(node).split(".").slice(1).join(".");
    }
    const componentExport = t.jsxAttribute(
      t.jsxNamespacedName(t.jsxIdentifier("client"), t.jsxIdentifier("component-export")),
      t.stringLiteral(meta.name)
    );
    node.openingElement.attributes.push(componentExport);
  }
  if (!existingAttributes.find((attr) => attr === "client:component-hydration")) {
    const staticMarker = t.jsxAttribute(
      t.jsxNamespacedName(t.jsxIdentifier("client"), t.jsxIdentifier("component-hydration"))
    );
    node.openingElement.attributes.push(staticMarker);
  }
}
function addClientOnlyMetadata(node, meta) {
  const tagName = getTagName(node);
  node.openingElement = t.jsxOpeningElement(
    t.jsxIdentifier(ClientOnlyPlaceholder),
    node.openingElement.attributes
  );
  if (node.closingElement) {
    node.closingElement = t.jsxClosingElement(t.jsxIdentifier(ClientOnlyPlaceholder));
  }
  const existingAttributes = node.openingElement.attributes.map(
    (attr) => t.isJSXAttribute(attr) ? jsxAttributeToString(attr) : null
  );
  if (!existingAttributes.find((attr) => attr === "client:display-name")) {
    const displayName = t.jsxAttribute(
      t.jsxNamespacedName(t.jsxIdentifier("client"), t.jsxIdentifier("display-name")),
      t.stringLiteral(tagName)
    );
    node.openingElement.attributes.push(displayName);
  }
  if (!existingAttributes.find((attr) => attr === "client:component-path")) {
    const componentPath = t.jsxAttribute(
      t.jsxNamespacedName(t.jsxIdentifier("client"), t.jsxIdentifier("component-path")),
      t.stringLiteral(meta.resolvedPath)
    );
    node.openingElement.attributes.push(componentPath);
  }
  if (!existingAttributes.find((attr) => attr === "client:component-export")) {
    if (meta.name === "*") {
      meta.name = getTagName(node).split(".").at(1);
    }
    const componentExport = t.jsxAttribute(
      t.jsxNamespacedName(t.jsxIdentifier("client"), t.jsxIdentifier("component-export")),
      t.stringLiteral(meta.name)
    );
    node.openingElement.attributes.push(componentExport);
  }
  if (!existingAttributes.find((attr) => attr === "client:component-hydration")) {
    const staticMarker = t.jsxAttribute(
      t.jsxNamespacedName(t.jsxIdentifier("client"), t.jsxIdentifier("component-hydration"))
    );
    node.openingElement.attributes.push(staticMarker);
  }
}
function astroJSX() {
  return {
    visitor: {
      Program: {
        enter(path, state) {
          if (!state.file.metadata.astro) {
            state.file.metadata.astro = createDefaultAstroMetadata();
          }
          path.node.body.splice(
            0,
            0,
            t.importDeclaration(
              [t.importSpecifier(t.identifier("Fragment"), t.identifier("Fragment"))],
              t.stringLiteral("astro/jsx-runtime")
            )
          );
        }
      },
      ImportDeclaration(path, state) {
        const source = path.node.source.value;
        if (source.startsWith("astro/jsx-runtime")) return;
        const specs = path.node.specifiers.map((spec) => {
          if (t.isImportDefaultSpecifier(spec))
            return { local: spec.local.name, imported: "default" };
          if (t.isImportNamespaceSpecifier(spec)) return { local: spec.local.name, imported: "*" };
          if (t.isIdentifier(spec.imported))
            return { local: spec.local.name, imported: spec.imported.name };
          return { local: spec.local.name, imported: spec.imported.value };
        });
        const imports = state.get("imports") ?? /* @__PURE__ */ new Map();
        for (const spec of specs) {
          if (imports.has(source)) {
            const existing = imports.get(source);
            existing.add(spec);
            imports.set(source, existing);
          } else {
            imports.set(source, /* @__PURE__ */ new Set([spec]));
          }
        }
        state.set("imports", imports);
      },
      JSXMemberExpression(path, state) {
        const node = path.node;
        if (state.filename?.endsWith(".mdx") && t.isJSXIdentifier(node.object) && node.object.name === "_components") {
          return;
        }
        const parent = path.findParent((n) => t.isJSXElement(n.node));
        const parentNode = parent.node;
        const tagName = getTagName(parentNode);
        if (!isComponent(tagName)) return;
        if (!hasClientDirective(parentNode)) return;
        const isClientOnly = isClientOnlyComponent(parentNode);
        if (tagName === ClientOnlyPlaceholder) return;
        const imports = state.get("imports") ?? /* @__PURE__ */ new Map();
        const namespace = tagName.split(".");
        for (const [source, specs] of imports) {
          for (const { imported, local } of specs) {
            const reference = path.referencesImport(source, imported);
            if (reference) {
              path.setData("import", { name: imported, path: source });
              break;
            }
            if (namespace.at(0) === local) {
              const name = imported === "*" ? imported : tagName;
              path.setData("import", { name, path: source });
              break;
            }
          }
        }
        const meta = path.getData("import");
        if (meta) {
          const resolvedPath = resolvePath(meta.path, state.filename);
          if (isClientOnly) {
            state.file.metadata.astro.clientOnlyComponents.push({
              exportName: meta.name,
              localName: "",
              specifier: tagName,
              resolvedPath
            });
            meta.resolvedPath = resolvedPath;
            addClientOnlyMetadata(parentNode, meta);
          } else {
            state.file.metadata.astro.hydratedComponents.push({
              exportName: "*",
              localName: "",
              specifier: tagName,
              resolvedPath
            });
            meta.resolvedPath = resolvedPath;
            addClientMetadata(parentNode, meta);
          }
        } else {
          throw new Error(
            `Unable to match <${getTagName(
              parentNode
            )}> with client:* directive to an import statement!`
          );
        }
      },
      JSXIdentifier(path, state) {
        const isAttr = path.findParent((n) => t.isJSXAttribute(n.node));
        if (isAttr) return;
        const parent = path.findParent((n) => t.isJSXElement(n.node));
        const parentNode = parent.node;
        const tagName = getTagName(parentNode);
        if (!isComponent(tagName)) return;
        if (!hasClientDirective(parentNode)) return;
        const isClientOnly = isClientOnlyComponent(parentNode);
        if (tagName === ClientOnlyPlaceholder) return;
        const imports = state.get("imports") ?? /* @__PURE__ */ new Map();
        const namespace = tagName.split(".");
        for (const [source, specs] of imports) {
          for (const { imported, local } of specs) {
            const reference = path.referencesImport(source, imported);
            if (reference) {
              path.setData("import", { name: imported, path: source });
              break;
            }
            if (namespace.at(0) === local) {
              path.setData("import", { name: imported, path: source });
              break;
            }
          }
        }
        const meta = path.getData("import");
        if (meta) {
          if (meta.path.endsWith(".astro")) {
            const displayName = getTagName(parentNode);
            for (const attr of parentNode.openingElement.attributes) {
              if (t.isJSXAttribute(attr)) {
                const name = jsxAttributeToString(attr);
                if (name.startsWith("client:")) {
                  console.warn(
                    `You are attempting to render <${displayName} ${name} />, but ${displayName} is an Astro component. Astro components do not render in the client and should not have a hydration directive. Please use a framework component for client rendering.`
                  );
                }
              }
            }
          }
          const resolvedPath = resolvePath(meta.path, state.filename);
          if (isClientOnly) {
            state.file.metadata.astro.clientOnlyComponents.push({
              exportName: meta.name,
              localName: "",
              specifier: meta.name,
              resolvedPath
            });
            meta.resolvedPath = resolvedPath;
            addClientOnlyMetadata(parentNode, meta);
          } else {
            state.file.metadata.astro.hydratedComponents.push({
              exportName: meta.name,
              localName: "",
              specifier: meta.name,
              resolvedPath
            });
            meta.resolvedPath = resolvedPath;
            addClientMetadata(parentNode, meta);
          }
        } else {
          throw new AstroError({
            ...AstroErrorData.NoMatchingImport,
            message: AstroErrorData.NoMatchingImport.message(getTagName(parentNode))
          });
        }
      }
    }
  };
}
export {
  astroJSX as default
};
