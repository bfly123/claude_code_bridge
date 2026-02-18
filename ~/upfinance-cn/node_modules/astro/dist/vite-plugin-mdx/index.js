import { transformWithEsbuild } from "vite";
import { CONTENT_FLAG, PROPAGATED_ASSET_FLAG } from "../content/index.js";
import { astroEntryPrefix } from "../core/build/plugins/plugin-component-entry.js";
import { removeQueryString } from "../core/path.js";
import { transformJSX } from "./transform-jsx.js";
const SPECIAL_QUERY_REGEX = new RegExp(
  `[?&](?:worker|sharedworker|raw|url|${CONTENT_FLAG}|${PROPAGATED_ASSET_FLAG})\\b`
);
function mdxVitePlugin() {
  return {
    name: "astro:jsx",
    enforce: "pre",
    // run transforms before other plugins
    async transform(code, id, opts) {
      if (SPECIAL_QUERY_REGEX.test(id) || id.startsWith(astroEntryPrefix)) {
        return null;
      }
      id = removeQueryString(id);
      if (!id.endsWith(".mdx")) {
        return null;
      }
      const { code: jsxCode } = await transformWithEsbuild(code, id, {
        loader: "jsx",
        jsx: "preserve",
        sourcemap: "inline",
        tsconfigRaw: {
          compilerOptions: {
            // Ensure client:only imports are treeshaken
            verbatimModuleSyntax: false,
            importsNotUsedAsValues: "remove"
          }
        }
      });
      return await transformJSX(jsxCode, id, opts?.ssr);
    }
  };
}
export {
  mdxVitePlugin as default
};
