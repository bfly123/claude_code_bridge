import { yellow } from "kleur/colors";
import { imageMetadata } from "../utils/metadata.js";
import {
  baseService,
  parseQuality
} from "./service.js";
import { processBuffer } from "./vendor/squoosh/image-pool.js";
console.warn(
  yellow(
    "The Squoosh image service is deprecated and will be removed in Astro 5.x. We suggest migrating to the default Sharp image service instead, as it is faster, more powerful and better maintained."
  )
);
const baseQuality = { low: 25, mid: 50, high: 80, max: 100 };
const qualityTable = {
  avif: {
    // Squoosh's AVIF encoder has a bit of a weird behavior where `62` is technically the maximum, and anything over is overkill
    max: 62,
    high: 45,
    mid: 35,
    low: 20
  },
  jpeg: baseQuality,
  jpg: baseQuality,
  webp: baseQuality
  // Squoosh's PNG encoder does not support a quality setting, so we can skip that here
};
async function getRotationForEXIF(inputBuffer, src) {
  const meta = await imageMetadata(inputBuffer, src);
  if (!meta) return void 0;
  switch (meta.orientation) {
    case 3:
    case 4:
      return { type: "rotate", numRotations: 2 };
    case 5:
    case 6:
      return { type: "rotate", numRotations: 1 };
    case 7:
    case 8:
      return { type: "rotate", numRotations: 3 };
    case void 0:
    default:
      return void 0;
  }
}
const service = {
  validateOptions: baseService.validateOptions,
  getURL: baseService.getURL,
  parseURL: baseService.parseURL,
  getHTMLAttributes: baseService.getHTMLAttributes,
  getSrcSet: baseService.getSrcSet,
  async transform(inputBuffer, transformOptions) {
    const transform = transformOptions;
    let format = transform.format;
    if (format === "svg") return { data: inputBuffer, format: "svg" };
    const operations = [];
    const rotation = await getRotationForEXIF(inputBuffer, transform.src);
    if (rotation) {
      operations.push(rotation);
    }
    if (transform.height && !transform.width) {
      operations.push({
        type: "resize",
        height: Math.round(transform.height)
      });
    } else if (transform.width) {
      operations.push({
        type: "resize",
        width: Math.round(transform.width)
      });
    }
    let quality = void 0;
    if (transform.quality) {
      const parsedQuality = parseQuality(transform.quality);
      if (typeof parsedQuality === "number") {
        quality = parsedQuality;
      } else {
        quality = transform.quality in qualityTable[format] ? qualityTable[format][transform.quality] : void 0;
      }
    }
    const data = await processBuffer(inputBuffer, operations, format, quality);
    return {
      data: Buffer.from(data),
      format
    };
  }
};
var squoosh_default = service;
export {
  squoosh_default as default
};
