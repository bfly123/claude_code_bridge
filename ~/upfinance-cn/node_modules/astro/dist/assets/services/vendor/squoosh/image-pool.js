import { cpus } from "node:os";
import { fileURLToPath } from "node:url";
import { isMainThread } from "node:worker_threads";
import { getModuleURL } from "./emscripten-utils.js";
import * as impl from "./impl.js";
import execOnce from "./utils/execOnce.js";
import WorkerPool from "./utils/workerPool.js";
const getWorker = execOnce(() => {
  return new WorkerPool(
    // There will be at most 7 workers needed since each worker will take
    // at least 1 operation type.
    Math.max(1, Math.min(cpus().length - 1, 7)),
    fileURLToPath(getModuleURL(import.meta.url))
  );
});
function handleJob(params) {
  switch (params.operation) {
    case "decode":
      return impl.decodeBuffer(params.buffer);
    case "resize":
      return impl.resize({
        image: params.imageData,
        width: params.width,
        height: params.height
      });
    case "rotate":
      return impl.rotate(params.imageData, params.numRotations);
    case "encodeavif":
      return impl.encodeAvif(params.imageData, { quality: params.quality });
    case "encodejpeg":
      return impl.encodeJpeg(params.imageData, { quality: params.quality });
    case "encodepng":
      return impl.encodePng(params.imageData);
    case "encodewebp":
      return impl.encodeWebp(params.imageData, { quality: params.quality });
    default:
      throw Error(`Invalid job "${params.operation}"`);
  }
}
async function processBuffer(buffer, operations, encoding, quality) {
  const worker = await getWorker();
  let imageData = await worker.dispatchJob({
    operation: "decode",
    buffer
  });
  for (const operation of operations) {
    if (operation.type === "rotate") {
      imageData = await worker.dispatchJob({
        operation: "rotate",
        imageData,
        numRotations: operation.numRotations
      });
    } else if (operation.type === "resize") {
      imageData = await worker.dispatchJob({
        operation: "resize",
        imageData,
        height: operation.height,
        width: operation.width
      });
    }
  }
  switch (encoding) {
    case "avif":
      return await worker.dispatchJob({
        operation: "encodeavif",
        imageData,
        quality
      });
    case "jpeg":
    case "jpg":
      return await worker.dispatchJob({
        operation: "encodejpeg",
        imageData,
        quality
      });
    case "png":
      return await worker.dispatchJob({
        operation: "encodepng",
        imageData
      });
    case "webp":
      return await worker.dispatchJob({
        operation: "encodewebp",
        imageData,
        quality
      });
    case "svg":
    default:
      throw Error(`Unsupported encoding format`);
  }
}
if (!isMainThread) {
  WorkerPool.useThisThreadAsWorker(handleJob);
}
export {
  processBuffer
};
