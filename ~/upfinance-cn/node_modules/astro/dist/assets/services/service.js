import { AstroError, AstroErrorData } from "../../core/errors/index.js";
import { isCoreRemotePath, joinPaths } from "../../core/path.js";
import { DEFAULT_HASH_PROPS, DEFAULT_OUTPUT_FORMAT, VALID_SUPPORTED_FORMATS } from "../consts.js";
import { isESMImportedImage } from "../utils/imageKind.js";
import { isRemoteAllowed } from "../utils/remotePattern.js";
function isLocalService(service) {
  if (!service) {
    return false;
  }
  return "transform" in service;
}
function parseQuality(quality) {
  let result = parseInt(quality);
  if (Number.isNaN(result)) {
    return quality;
  }
  return result;
}
const baseService = {
  propertiesToHash: DEFAULT_HASH_PROPS,
  validateOptions(options) {
    if (!options.src || typeof options.src !== "string" && typeof options.src !== "object") {
      throw new AstroError({
        ...AstroErrorData.ExpectedImage,
        message: AstroErrorData.ExpectedImage.message(
          JSON.stringify(options.src),
          typeof options.src,
          JSON.stringify(options, (_, v) => v === void 0 ? null : v)
        )
      });
    }
    if (!isESMImportedImage(options.src)) {
      if (options.src.startsWith("/@fs/") || !isCoreRemotePath(options.src) && !options.src.startsWith("/")) {
        throw new AstroError({
          ...AstroErrorData.LocalImageUsedWrongly,
          message: AstroErrorData.LocalImageUsedWrongly.message(options.src)
        });
      }
      let missingDimension;
      if (!options.width && !options.height) {
        missingDimension = "both";
      } else if (!options.width && options.height) {
        missingDimension = "width";
      } else if (options.width && !options.height) {
        missingDimension = "height";
      }
      if (missingDimension) {
        throw new AstroError({
          ...AstroErrorData.MissingImageDimension,
          message: AstroErrorData.MissingImageDimension.message(missingDimension, options.src)
        });
      }
    } else {
      if (!VALID_SUPPORTED_FORMATS.includes(options.src.format)) {
        throw new AstroError({
          ...AstroErrorData.UnsupportedImageFormat,
          message: AstroErrorData.UnsupportedImageFormat.message(
            options.src.format,
            options.src.src,
            VALID_SUPPORTED_FORMATS
          )
        });
      }
      if (options.widths && options.densities) {
        throw new AstroError(AstroErrorData.IncompatibleDescriptorOptions);
      }
      if (options.src.format === "svg") {
        options.format = "svg";
      }
      if (options.src.format === "svg" && options.format !== "svg" || options.src.format !== "svg" && options.format === "svg") {
        throw new AstroError(AstroErrorData.UnsupportedImageConversion);
      }
    }
    if (!options.format) {
      options.format = DEFAULT_OUTPUT_FORMAT;
    }
    if (options.width) options.width = Math.round(options.width);
    if (options.height) options.height = Math.round(options.height);
    return options;
  },
  getHTMLAttributes(options) {
    const { targetWidth, targetHeight } = getTargetDimensions(options);
    const { src, width, height, format, quality, densities, widths, formats, ...attributes } = options;
    return {
      ...attributes,
      width: targetWidth,
      height: targetHeight,
      loading: attributes.loading ?? "lazy",
      decoding: attributes.decoding ?? "async"
    };
  },
  getSrcSet(options) {
    const srcSet = [];
    const { targetWidth } = getTargetDimensions(options);
    const { widths, densities } = options;
    const targetFormat = options.format ?? DEFAULT_OUTPUT_FORMAT;
    let imageWidth = options.width;
    let maxWidth = Infinity;
    if (isESMImportedImage(options.src)) {
      imageWidth = options.src.width;
      maxWidth = imageWidth;
    }
    const {
      width: transformWidth,
      height: transformHeight,
      ...transformWithoutDimensions
    } = options;
    const allWidths = [];
    if (densities) {
      const densityValues = densities.map((density) => {
        if (typeof density === "number") {
          return density;
        } else {
          return parseFloat(density);
        }
      });
      const densityWidths = densityValues.sort().map((density) => Math.round(targetWidth * density));
      allWidths.push(
        ...densityWidths.map((width, index) => ({
          maxTargetWidth: Math.min(width, maxWidth),
          descriptor: `${densityValues[index]}x`
        }))
      );
    } else if (widths) {
      allWidths.push(
        ...widths.map((width) => ({
          maxTargetWidth: Math.min(width, maxWidth),
          descriptor: `${width}w`
        }))
      );
    }
    for (const { maxTargetWidth, descriptor } of allWidths) {
      const srcSetTransform = { ...transformWithoutDimensions };
      if (maxTargetWidth !== imageWidth) {
        srcSetTransform.width = maxTargetWidth;
      } else {
        if (options.width && options.height) {
          srcSetTransform.width = options.width;
          srcSetTransform.height = options.height;
        }
      }
      srcSet.push({
        transform: srcSetTransform,
        descriptor,
        attributes: {
          type: `image/${targetFormat}`
        }
      });
    }
    return srcSet;
  },
  getURL(options, imageConfig) {
    const searchParams = new URLSearchParams();
    if (isESMImportedImage(options.src)) {
      searchParams.append("href", options.src.src);
    } else if (isRemoteAllowed(options.src, imageConfig)) {
      searchParams.append("href", options.src);
    } else {
      return options.src;
    }
    const params = {
      w: "width",
      h: "height",
      q: "quality",
      f: "format"
    };
    Object.entries(params).forEach(([param, key]) => {
      options[key] && searchParams.append(param, options[key].toString());
    });
    const imageEndpoint = joinPaths(import.meta.env.BASE_URL, "/_image");
    return `${imageEndpoint}?${searchParams}`;
  },
  parseURL(url) {
    const params = url.searchParams;
    if (!params.has("href")) {
      return void 0;
    }
    const transform = {
      src: params.get("href"),
      width: params.has("w") ? parseInt(params.get("w")) : void 0,
      height: params.has("h") ? parseInt(params.get("h")) : void 0,
      format: params.get("f"),
      quality: params.get("q")
    };
    return transform;
  }
};
function getTargetDimensions(options) {
  let targetWidth = options.width;
  let targetHeight = options.height;
  if (isESMImportedImage(options.src)) {
    const aspectRatio = options.src.width / options.src.height;
    if (targetHeight && !targetWidth) {
      targetWidth = Math.round(targetHeight * aspectRatio);
    } else if (targetWidth && !targetHeight) {
      targetHeight = Math.round(targetWidth / aspectRatio);
    } else if (!targetWidth && !targetHeight) {
      targetWidth = options.src.width;
      targetHeight = options.src.height;
    }
  }
  return {
    targetWidth,
    targetHeight
  };
}
export {
  baseService,
  isLocalService,
  parseQuality
};
