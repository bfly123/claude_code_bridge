import {
  createCssVariablesTheme,
  getHighlighter,
  isSpecialLang
} from "shiki";
import { visit } from "unist-util-visit";
const ASTRO_COLOR_REPLACEMENTS = {
  "--astro-code-foreground": "--astro-code-color-text",
  "--astro-code-background": "--astro-code-color-background"
};
const COLOR_REPLACEMENT_REGEX = new RegExp(
  `${Object.keys(ASTRO_COLOR_REPLACEMENTS).join("|")}`,
  "g"
);
let _cssVariablesTheme;
const cssVariablesTheme = () => _cssVariablesTheme ?? (_cssVariablesTheme = createCssVariablesTheme({ variablePrefix: "--astro-code-" }));
async function createShikiHighlighter({
  langs = [],
  theme = "github-dark",
  themes = {},
  defaultColor,
  wrap = false,
  transformers = [],
  langAlias = {}
} = {}) {
  theme = theme === "css-variables" ? cssVariablesTheme() : theme;
  const highlighter = await getHighlighter({
    langs: ["plaintext", ...langs],
    langAlias,
    themes: Object.values(themes).length ? Object.values(themes) : [theme]
  });
  return {
    async highlight(code, lang = "plaintext", options) {
      const resolvedLang = langAlias[lang] ?? lang;
      const loadedLanguages = highlighter.getLoadedLanguages();
      if (!isSpecialLang(lang) && !loadedLanguages.includes(resolvedLang)) {
        try {
          await highlighter.loadLanguage(resolvedLang);
        } catch (_err) {
          const langStr = lang === resolvedLang ? `"${lang}"` : `"${lang}" (aliased to "${resolvedLang}")`;
          console.warn(
            `[Shiki] The language ${langStr} doesn't exist, falling back to "plaintext".`
          );
          lang = "plaintext";
        }
      }
      const themeOptions = Object.values(themes).length ? { themes } : { theme };
      const inline = options?.inline ?? false;
      return highlighter.codeToHtml(code, {
        ...themeOptions,
        defaultColor,
        lang,
        // NOTE: while we can spread `options.attributes` here so that Shiki can auto-serialize this as rendered
        // attributes on the top-level tag, it's not clear whether it is fine to pass all attributes as meta, as
        // they're technically not meta, nor parsed from Shiki's `parseMetaString` API.
        meta: options?.meta ? { __raw: options?.meta } : void 0,
        transformers: [
          {
            pre(node) {
              if (inline) {
                node.tagName = "code";
              }
              const {
                class: attributesClass,
                style: attributesStyle,
                ...rest
              } = options?.attributes ?? {};
              Object.assign(node.properties, rest);
              const classValue = (normalizePropAsString(node.properties.class) ?? "") + (attributesClass ? ` ${attributesClass}` : "");
              const styleValue = (normalizePropAsString(node.properties.style) ?? "") + (attributesStyle ? `; ${attributesStyle}` : "");
              node.properties.class = classValue.replace(/shiki/g, "astro-code");
              node.properties.dataLanguage = lang;
              if (wrap === false) {
                node.properties.style = styleValue + "; overflow-x: auto;";
              } else if (wrap === true) {
                node.properties.style = styleValue + "; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word;";
              }
            },
            line(node) {
              if (resolvedLang === "diff") {
                const innerSpanNode = node.children[0];
                const innerSpanTextNode = innerSpanNode?.type === "element" && innerSpanNode.children?.[0];
                if (innerSpanTextNode && innerSpanTextNode.type === "text") {
                  const start = innerSpanTextNode.value[0];
                  if (start === "+" || start === "-") {
                    innerSpanTextNode.value = innerSpanTextNode.value.slice(1);
                    innerSpanNode.children.unshift({
                      type: "element",
                      tagName: "span",
                      properties: { style: "user-select: none;" },
                      children: [{ type: "text", value: start }]
                    });
                  }
                }
              }
            },
            code(node) {
              if (inline) {
                return node.children[0];
              }
            },
            root(node) {
              if (Object.values(themes).length) {
                return;
              }
              const themeName = typeof theme === "string" ? theme : theme.name;
              if (themeName === "css-variables") {
                visit(node, "element", (child) => {
                  if (child.properties?.style) {
                    child.properties.style = replaceCssVariables(child.properties.style);
                  }
                });
              }
            }
          },
          ...transformers
        ]
      });
    }
  };
}
function normalizePropAsString(value) {
  return Array.isArray(value) ? value.join(" ") : value;
}
function replaceCssVariables(str) {
  return str.replace(COLOR_REPLACEMENT_REGEX, (match) => ASTRO_COLOR_REPLACEMENTS[match] || match);
}
export {
  createShikiHighlighter
};
