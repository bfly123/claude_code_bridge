import CachePolicy from "http-cache-semantics";
async function loadRemoteImage(src) {
  const req = new Request(src);
  const res = await fetch(req);
  if (!res.ok) {
    throw new Error(
      `Failed to load remote image ${src}. The request did not return a 200 OK response. (received ${res.status}))`
    );
  }
  const policy = new CachePolicy(webToCachePolicyRequest(req), webToCachePolicyResponse(res));
  const expires = policy.storable() ? policy.timeToLive() : 0;
  return {
    data: Buffer.from(await res.arrayBuffer()),
    expires: Date.now() + expires
  };
}
function webToCachePolicyRequest({ url, method, headers: _headers }) {
  let headers = {};
  try {
    headers = Object.fromEntries(_headers.entries());
  } catch {
  }
  return {
    method,
    url,
    headers
  };
}
function webToCachePolicyResponse({ status, headers: _headers }) {
  let headers = {};
  try {
    headers = Object.fromEntries(_headers.entries());
  } catch {
  }
  return {
    status,
    headers
  };
}
export {
  loadRemoteImage
};
