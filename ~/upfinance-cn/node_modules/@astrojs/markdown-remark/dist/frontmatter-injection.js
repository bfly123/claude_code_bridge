function isValidAstroData(obj) {
  if (typeof obj === "object" && obj !== null && obj.hasOwnProperty("frontmatter")) {
    const { frontmatter } = obj;
    try {
      JSON.stringify(frontmatter);
    } catch {
      return false;
    }
    return typeof frontmatter === "object" && frontmatter !== null;
  }
  return false;
}
class InvalidAstroDataError extends TypeError {
}
function safelyGetAstroData(vfileData) {
  const { astro } = vfileData;
  if (!astro || !isValidAstroData(astro)) {
    return new InvalidAstroDataError();
  }
  return astro;
}
function setVfileFrontmatter(vfile, frontmatter) {
  vfile.data ??= {};
  vfile.data.astro ??= {};
  vfile.data.astro.frontmatter = frontmatter;
}
export {
  InvalidAstroDataError,
  safelyGetAstroData,
  setVfileFrontmatter
};
