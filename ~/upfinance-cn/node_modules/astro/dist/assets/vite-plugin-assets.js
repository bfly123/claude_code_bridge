import { extname } from "node:path";
import MagicString from "magic-string";
import { normalizePath } from "vite";
import { extendManualChunks } from "../core/build/plugins/util.js";
import { AstroError, AstroErrorData } from "../core/errors/index.js";
import {
  appendForwardSlash,
  joinPaths,
  prependForwardSlash,
  removeBase,
  removeQueryString
} from "../core/path.js";
import { isServerLikeOutput } from "../core/util.js";
import { VALID_INPUT_FORMATS, VIRTUAL_MODULE_ID, VIRTUAL_SERVICE_ID } from "./consts.js";
import { getAssetsPrefix } from "./utils/getAssetsPrefix.js";
import { isESMImportedImage } from "./utils/imageKind.js";
import { emitESMImage } from "./utils/node/emitAsset.js";
import { getProxyCode } from "./utils/proxy.js";
import { hashTransform, propsToFilename } from "./utils/transformToPath.js";
const resolvedVirtualModuleId = "\0" + VIRTUAL_MODULE_ID;
const assetRegex = new RegExp(`\\.(${VALID_INPUT_FORMATS.join("|")})`, "i");
const assetRegexEnds = new RegExp(`\\.(${VALID_INPUT_FORMATS.join("|")})$`, "i");
const addStaticImageFactory = (settings) => {
  return (options, hashProperties, originalFSPath) => {
    if (!globalThis.astroAsset.staticImages) {
      globalThis.astroAsset.staticImages = /* @__PURE__ */ new Map();
    }
    const ESMImportedImageSrc = isESMImportedImage(options.src) ? options.src.src : options.src;
    const fileExtension = extname(ESMImportedImageSrc);
    const assetPrefix = getAssetsPrefix(fileExtension, settings.config.build.assetsPrefix);
    const finalOriginalPath = removeBase(
      removeBase(ESMImportedImageSrc, settings.config.base),
      assetPrefix
    );
    const hash = hashTransform(options, settings.config.image.service.entrypoint, hashProperties);
    let finalFilePath;
    let transformsForPath = globalThis.astroAsset.staticImages.get(finalOriginalPath);
    let transformForHash = transformsForPath?.transforms.get(hash);
    if (transformsForPath && transformForHash) {
      finalFilePath = transformForHash.finalPath;
    } else {
      finalFilePath = prependForwardSlash(
        joinPaths(
          isESMImportedImage(options.src) ? "" : settings.config.build.assets,
          prependForwardSlash(propsToFilename(finalOriginalPath, options, hash))
        )
      );
      if (!transformsForPath) {
        globalThis.astroAsset.staticImages.set(finalOriginalPath, {
          originalSrcPath: originalFSPath,
          transforms: /* @__PURE__ */ new Map()
        });
        transformsForPath = globalThis.astroAsset.staticImages.get(finalOriginalPath);
      }
      transformsForPath.transforms.set(hash, {
        finalPath: finalFilePath,
        transform: options
      });
    }
    if (settings.config.build.assetsPrefix) {
      return encodeURI(joinPaths(assetPrefix, finalFilePath));
    } else {
      return encodeURI(prependForwardSlash(joinPaths(settings.config.base, finalFilePath)));
    }
  };
};
function assets({
  settings,
  mode
}) {
  let resolvedConfig;
  let shouldEmitFile = false;
  globalThis.astroAsset = {
    referencedImages: /* @__PURE__ */ new Set()
  };
  return [
    // Expose the components and different utilities from `astro:assets` and handle serving images from `/_image` in dev
    {
      name: "astro:assets",
      outputOptions(outputOptions) {
        extendManualChunks(outputOptions, {
          after(id) {
            if (id.includes("astro/dist/assets/services/")) {
              return `astro/assets-service`;
            }
          }
        });
      },
      async resolveId(id) {
        if (id === VIRTUAL_SERVICE_ID) {
          return await this.resolve(settings.config.image.service.entrypoint);
        }
        if (id === VIRTUAL_MODULE_ID) {
          return resolvedVirtualModuleId;
        }
      },
      load(id) {
        if (id === resolvedVirtualModuleId) {
          return `
					export { getConfiguredImageService, isLocalService } from "astro/assets";
					import { getImage as getImageInternal } from "astro/assets";
					export { default as Image } from "astro/components/Image.astro";
					export { default as Picture } from "astro/components/Picture.astro";
					export { inferRemoteSize } from "astro/assets/utils/inferRemoteSize.js";

					export const imageConfig = ${JSON.stringify(settings.config.image)};
					// This is used by the @astrojs/node integration to locate images.
					// It's unused on other platforms, but on some platforms like Netlify (and presumably also Vercel)
					// new URL("dist/...") is interpreted by the bundler as a signal to include that directory
					// in the Lambda bundle, which would bloat the bundle with images.
					// To prevent this, we mark the URL construction as pure,
					// so that it's tree-shaken away for all platforms that don't need it.
					export const outDir = /* #__PURE__ */ new URL(${JSON.stringify(
            new URL(
              isServerLikeOutput(settings.config) ? settings.config.build.client : settings.config.outDir
            )
          )});
					export const assetsDir = /* #__PURE__ */ new URL(${JSON.stringify(
            settings.config.build.assets
          )}, outDir);
					export const getImage = async (options) => await getImageInternal(options, imageConfig);
				`;
        }
      },
      buildStart() {
        if (mode != "build") {
          return;
        }
        globalThis.astroAsset.addStaticImage = addStaticImageFactory(settings);
      },
      // In build, rewrite paths to ESM imported images in code to their final location
      async renderChunk(code) {
        const assetUrlRE = /__ASTRO_ASSET_IMAGE__([\w$]{8})__(?:_(.*?)__)?/g;
        let match;
        let s;
        while (match = assetUrlRE.exec(code)) {
          s = s || (s = new MagicString(code));
          const [full, hash, postfix = ""] = match;
          const file = this.getFileName(hash);
          const fileExtension = extname(file);
          const pf = getAssetsPrefix(fileExtension, settings.config.build.assetsPrefix);
          const prefix = pf ? appendForwardSlash(pf) : resolvedConfig.base;
          const outputFilepath = prefix + normalizePath(file + postfix);
          s.overwrite(match.index, match.index + full.length, outputFilepath);
        }
        if (s) {
          return {
            code: s.toString(),
            map: resolvedConfig.build.sourcemap ? s.generateMap({ hires: "boundary" }) : null
          };
        } else {
          return null;
        }
      }
    },
    // Return a more advanced shape for images imported in ESM
    {
      name: "astro:assets:esm",
      enforce: "pre",
      config(_, env) {
        shouldEmitFile = env.command === "build";
      },
      configResolved(viteConfig) {
        resolvedConfig = viteConfig;
      },
      async load(id, options) {
        if (assetRegex.test(id)) {
          if (!globalThis.astroAsset.referencedImages)
            globalThis.astroAsset.referencedImages = /* @__PURE__ */ new Set();
          if (id !== removeQueryString(id)) {
            globalThis.astroAsset.referencedImages.add(removeQueryString(id));
            return;
          }
          if (!assetRegexEnds.test(id)) {
            return;
          }
          const emitFile = shouldEmitFile ? this.emitFile : void 0;
          const imageMetadata = await emitESMImage(id, this.meta.watchMode, emitFile);
          if (!imageMetadata) {
            throw new AstroError({
              ...AstroErrorData.ImageNotFound,
              message: AstroErrorData.ImageNotFound.message(id)
            });
          }
          if (options?.ssr) {
            return `export default ${getProxyCode(
              imageMetadata,
              isServerLikeOutput(settings.config)
            )}`;
          } else {
            globalThis.astroAsset.referencedImages.add(imageMetadata.fsPath);
            return `export default ${JSON.stringify(imageMetadata)}`;
          }
        }
      }
    }
  ];
}
export {
  assets as default
};
