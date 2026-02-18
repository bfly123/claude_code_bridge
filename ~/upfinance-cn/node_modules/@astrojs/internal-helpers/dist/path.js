function appendExtension(path, extension) {
  return path + "." + extension;
}
function appendForwardSlash(path) {
  return path.endsWith("/") ? path : path + "/";
}
function prependForwardSlash(path) {
  return path[0] === "/" ? path : "/" + path;
}
function collapseDuplicateSlashes(path) {
  return path.replace(/(?<!:)\/{2,}/g, "/");
}
function removeTrailingForwardSlash(path) {
  return path.endsWith("/") ? path.slice(0, path.length - 1) : path;
}
function removeLeadingForwardSlash(path) {
  return path.startsWith("/") ? path.substring(1) : path;
}
function removeLeadingForwardSlashWindows(path) {
  return path.startsWith("/") && path[2] === ":" ? path.substring(1) : path;
}
function trimSlashes(path) {
  return path.replace(/^\/|\/$/g, "");
}
function startsWithForwardSlash(path) {
  return path[0] === "/";
}
function startsWithDotDotSlash(path) {
  const c1 = path[0];
  const c2 = path[1];
  const c3 = path[2];
  return c1 === "." && c2 === "." && c3 === "/";
}
function startsWithDotSlash(path) {
  const c1 = path[0];
  const c2 = path[1];
  return c1 === "." && c2 === "/";
}
function isRelativePath(path) {
  return startsWithDotDotSlash(path) || startsWithDotSlash(path);
}
function isString(path) {
  return typeof path === "string" || path instanceof String;
}
function joinPaths(...paths) {
  return paths.filter(isString).map((path, i) => {
    if (i === 0) {
      return removeTrailingForwardSlash(path);
    } else if (i === paths.length - 1) {
      return removeLeadingForwardSlash(path);
    } else {
      return trimSlashes(path);
    }
  }).join("/");
}
function removeFileExtension(path) {
  let idx = path.lastIndexOf(".");
  return idx === -1 ? path : path.slice(0, idx);
}
function removeQueryString(path) {
  const index = path.lastIndexOf("?");
  return index > 0 ? path.substring(0, index) : path;
}
function isRemotePath(src) {
  return /^(?:http|ftp|https|ws):?\/\//.test(src) || src.startsWith("data:");
}
function slash(path) {
  return path.replace(/\\/g, "/");
}
function fileExtension(path) {
  const ext = path.split(".").pop();
  return ext !== path ? `.${ext}` : "";
}
function removeBase(path, base) {
  if (path.startsWith(base)) {
    return path.slice(removeTrailingForwardSlash(base).length);
  }
  return path;
}
export {
  appendExtension,
  appendForwardSlash,
  collapseDuplicateSlashes,
  fileExtension,
  isRelativePath,
  isRemotePath,
  joinPaths,
  prependForwardSlash,
  removeBase,
  removeFileExtension,
  removeLeadingForwardSlash,
  removeLeadingForwardSlashWindows,
  removeQueryString,
  removeTrailingForwardSlash,
  slash,
  startsWithDotDotSlash,
  startsWithDotSlash,
  startsWithForwardSlash,
  trimSlashes
};
