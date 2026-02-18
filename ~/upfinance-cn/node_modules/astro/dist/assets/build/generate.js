import fs, { readFileSync } from "node:fs";
import { basename } from "node:path/posix";
import { dim, green } from "kleur/colors";
import { getOutDirWithinCwd } from "../../core/build/common.js";
import { getTimeStat } from "../../core/build/util.js";
import { AstroError } from "../../core/errors/errors.js";
import { AstroErrorData } from "../../core/errors/index.js";
import { isCoreRemotePath, isRemotePath, removeLeadingForwardSlash } from "../../core/path.js";
import { isServerLikeOutput } from "../../core/util.js";
import { getConfiguredImageService } from "../internal.js";
import { isESMImportedImage } from "../utils/imageKind.js";
import { loadRemoteImage } from "./remote.js";
async function prepareAssetsGenerationEnv(pipeline, totalCount) {
  const { config, logger } = pipeline;
  let useCache = true;
  const assetsCacheDir = new URL("assets/", config.cacheDir);
  const count = { total: totalCount, current: 1 };
  try {
    await fs.promises.mkdir(assetsCacheDir, { recursive: true });
  } catch (err) {
    logger.warn(
      null,
      `An error was encountered while creating the cache directory. Proceeding without caching. Error: ${err}`
    );
    useCache = false;
  }
  let serverRoot, clientRoot;
  if (isServerLikeOutput(config)) {
    serverRoot = config.build.server;
    clientRoot = config.build.client;
  } else {
    serverRoot = getOutDirWithinCwd(config.outDir);
    clientRoot = config.outDir;
  }
  return {
    logger,
    isSSR: isServerLikeOutput(config),
    count,
    useCache,
    assetsCacheDir,
    serverRoot,
    clientRoot,
    imageConfig: config.image,
    assetsFolder: config.build.assets
  };
}
function getFullImagePath(originalFilePath, env) {
  return new URL(removeLeadingForwardSlash(originalFilePath), env.serverRoot);
}
async function generateImagesForPath(originalFilePath, transformsAndPath, env, queue) {
  let originalImage;
  for (const [_, transform] of transformsAndPath.transforms) {
    await queue.add(async () => generateImage(transform.finalPath, transform.transform)).catch((e) => {
      throw e;
    });
  }
  if (!env.isSSR && transformsAndPath.originalSrcPath && !globalThis.astroAsset.referencedImages?.has(transformsAndPath.originalSrcPath)) {
    try {
      if (transformsAndPath.originalSrcPath) {
        env.logger.debug(
          "assets",
          `Deleting ${originalFilePath} as it's not referenced outside of image processing.`
        );
        await fs.promises.unlink(getFullImagePath(originalFilePath, env));
      }
    } catch {
    }
  }
  async function generateImage(filepath, options) {
    const timeStart = performance.now();
    const generationData = await generateImageInternal(filepath, options);
    const timeEnd = performance.now();
    const timeChange = getTimeStat(timeStart, timeEnd);
    const timeIncrease = `(+${timeChange})`;
    const statsText = generationData.cached ? `(reused cache entry)` : `(before: ${generationData.weight.before}kB, after: ${generationData.weight.after}kB)`;
    const count = `(${env.count.current}/${env.count.total})`;
    env.logger.info(
      null,
      `  ${green("\u25B6")} ${filepath} ${dim(statsText)} ${dim(timeIncrease)} ${dim(count)}`
    );
    env.count.current++;
  }
  async function generateImageInternal(filepath, options) {
    const isLocalImage = isESMImportedImage(options.src);
    const finalFileURL = new URL("." + filepath, env.clientRoot);
    const finalFolderURL = new URL("./", finalFileURL);
    await fs.promises.mkdir(finalFolderURL, { recursive: true });
    const cacheFile = basename(filepath) + (isLocalImage ? "" : ".json");
    const cachedFileURL = new URL(cacheFile, env.assetsCacheDir);
    try {
      if (isLocalImage) {
        await fs.promises.copyFile(cachedFileURL, finalFileURL, fs.constants.COPYFILE_FICLONE);
        return {
          cached: true
        };
      } else {
        const JSONData = JSON.parse(readFileSync(cachedFileURL, "utf-8"));
        if (!JSONData.data || !JSONData.expires) {
          await fs.promises.unlink(cachedFileURL);
          throw new Error(
            `Malformed cache entry for ${filepath}, cache will be regenerated for this file.`
          );
        }
        if (JSONData.expires > Date.now()) {
          await fs.promises.writeFile(finalFileURL, Buffer.from(JSONData.data, "base64"));
          return {
            cached: true
          };
        } else {
          await fs.promises.unlink(cachedFileURL);
        }
      }
    } catch (e) {
      if (e.code !== "ENOENT") {
        throw new Error(`An error was encountered while reading the cache file. Error: ${e}`);
      }
    }
    const originalImagePath = isLocalImage ? options.src.src : options.src;
    if (!originalImage) {
      originalImage = await loadImage(originalFilePath, env);
    }
    let resultData = {
      data: void 0,
      expires: originalImage.expires
    };
    const imageService = await getConfiguredImageService();
    try {
      resultData.data = (await imageService.transform(
        originalImage.data,
        { ...options, src: originalImagePath },
        env.imageConfig
      )).data;
    } catch (e) {
      const error = new AstroError(
        {
          ...AstroErrorData.CouldNotTransformImage,
          message: AstroErrorData.CouldNotTransformImage.message(originalFilePath)
        },
        { cause: e }
      );
      throw error;
    }
    try {
      if (env.useCache) {
        if (isLocalImage) {
          await fs.promises.writeFile(cachedFileURL, resultData.data);
        } else {
          await fs.promises.writeFile(
            cachedFileURL,
            JSON.stringify({
              data: Buffer.from(resultData.data).toString("base64"),
              expires: resultData.expires
            })
          );
        }
      }
    } catch (e) {
      env.logger.warn(
        null,
        `An error was encountered while creating the cache directory. Proceeding without caching. Error: ${e}`
      );
    } finally {
      await fs.promises.writeFile(finalFileURL, resultData.data);
    }
    return {
      cached: false,
      weight: {
        // Divide by 1024 to get size in kilobytes
        before: Math.trunc(originalImage.data.byteLength / 1024),
        after: Math.trunc(Buffer.from(resultData.data).byteLength / 1024)
      }
    };
  }
}
function getStaticImageList() {
  if (!globalThis?.astroAsset?.staticImages) {
    return /* @__PURE__ */ new Map();
  }
  return globalThis.astroAsset.staticImages;
}
async function loadImage(path, env) {
  if (isCoreRemotePath(path)) {
    const remoteImage = await loadRemoteImage(path);
    return {
      data: remoteImage.data,
      expires: remoteImage.expires
    };
  }
  return {
    data: await fs.promises.readFile(getFullImagePath(path, env)),
    expires: 0
  };
}
export {
  generateImagesForPath,
  getStaticImageList,
  prepareAssetsGenerationEnv
};
