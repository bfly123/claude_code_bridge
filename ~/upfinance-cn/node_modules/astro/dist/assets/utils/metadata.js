import { AstroError, AstroErrorData } from "../../core/errors/index.js";
import { lookup as probe } from "../utils/vendor/image-size/lookup.js";
async function imageMetadata(data, src) {
  try {
    const result = probe(data);
    if (!result.height || !result.width || !result.type) {
      throw new AstroError({
        ...AstroErrorData.NoImageMetadata,
        message: AstroErrorData.NoImageMetadata.message(src)
      });
    }
    const { width, height, type, orientation } = result;
    const isPortrait = (orientation || 0) >= 5;
    return {
      width: isPortrait ? height : width,
      height: isPortrait ? width : height,
      format: type,
      orientation
    };
  } catch {
    throw new AstroError({
      ...AstroErrorData.NoImageMetadata,
      message: AstroErrorData.NoImageMetadata.message(src)
    });
  }
}
export {
  imageMetadata
};
