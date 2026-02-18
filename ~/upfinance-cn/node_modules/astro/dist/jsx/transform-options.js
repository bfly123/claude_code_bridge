async function jsxTransformOptions() {
  const plugin = await import("@babel/plugin-transform-react-jsx");
  const jsx = plugin.default?.default ?? plugin.default;
  const { default: astroJSX } = await import("./babel.js");
  return {
    plugins: [
      astroJSX(),
      jsx({}, { throwIfNamespace: false, runtime: "automatic", importSource: "astro" })
    ]
  };
}
export {
  jsxTransformOptions
};
