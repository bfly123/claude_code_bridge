import { isRemotePath as _externalIsRemotePath } from "@astrojs/internal-helpers/path";
export * from "@astrojs/internal-helpers/path";
const URL_PROTOCOL_REGEX = /^(?:(?:http|ftp|https|ws):?\/\/|\/\/)/;
function isCoreRemotePath(path) {
  return URL_PROTOCOL_REGEX.test(path) || _externalIsRemotePath(path);
}
export {
  isCoreRemotePath
};
