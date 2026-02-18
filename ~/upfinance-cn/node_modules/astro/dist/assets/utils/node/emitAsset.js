import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { prependForwardSlash, slash } from "../../../core/path.js";
import { imageMetadata } from "../metadata.js";
async function emitESMImage(id, _watchMode, fileEmitter) {
  if (!id) {
    return void 0;
  }
  const url = pathToFileURL(id);
  let fileData;
  try {
    fileData = await fs.readFile(url);
  } catch {
    return void 0;
  }
  const fileMetadata = await imageMetadata(fileData, id);
  const emittedImage = {
    src: "",
    ...fileMetadata
  };
  Object.defineProperty(emittedImage, "fsPath", {
    enumerable: false,
    writable: false,
    value: id
  });
  let isBuild = typeof fileEmitter === "function";
  if (isBuild) {
    const pathname = decodeURI(url.pathname);
    const filename = path.basename(pathname, path.extname(pathname) + `.${fileMetadata.format}`);
    try {
      const handle = fileEmitter({
        name: filename,
        source: await fs.readFile(url),
        type: "asset"
      });
      emittedImage.src = `__ASTRO_ASSET_IMAGE__${handle}__`;
    } catch {
      isBuild = false;
    }
  }
  if (!isBuild) {
    url.searchParams.append("origWidth", fileMetadata.width.toString());
    url.searchParams.append("origHeight", fileMetadata.height.toString());
    url.searchParams.append("origFormat", fileMetadata.format);
    emittedImage.src = `/@fs` + prependForwardSlash(fileURLToNormalizedPath(url));
  }
  return emittedImage;
}
function fileURLToNormalizedPath(filePath) {
  return slash(fileURLToPath(filePath) + filePath.search).replace(/\\/g, "/");
}
export {
  emitESMImage
};
