function injectImageEndpoint(settings, mode) {
  const endpointEntrypoint = settings.config.image.endpoint ?? (mode === "dev" ? "astro/assets/endpoint/node" : "astro/assets/endpoint/generic");
  settings.injectedRoutes.push({
    pattern: "/_image",
    entrypoint: endpointEntrypoint,
    prerender: false
  });
  return settings;
}
export {
  injectImageEndpoint
};
