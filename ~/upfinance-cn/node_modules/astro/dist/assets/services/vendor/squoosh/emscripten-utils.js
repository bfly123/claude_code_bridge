import { fileURLToPath, pathToFileURL } from "node:url";
function pathify(path) {
  if (path.startsWith("file://")) {
    path = fileURLToPath(path);
  }
  return path;
}
function instantiateEmscriptenWasm(factory, bytes) {
  return factory({
    // @ts-expect-error This is a valid Emscripten option, but the type definitions don't know about it
    wasmBinary: bytes,
    locateFile(file) {
      return file;
    }
  });
}
function dirname(url) {
  return url.substring(0, url.lastIndexOf("/"));
}
function getModuleURL(url) {
  if (!url) {
    return pathToFileURL(__filename).toString();
  }
  return url;
}
export {
  dirname,
  getModuleURL,
  instantiateEmscriptenWasm,
  pathify
};
