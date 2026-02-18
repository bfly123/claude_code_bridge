import type { AstroConfig, RouteData } from '../../@types/astro.js';
export declare function getOutFolder(astroConfig: AstroConfig, pathname: string, routeData: RouteData): URL;
export declare function getOutFile(astroConfig: AstroConfig, outFolder: URL, pathname: string, routeData: RouteData): URL;
/**
 * Ensures the `outDir` is within `process.cwd()`. If not it will fallback to `<cwd>/.astro`.
 * This is used for static `ssrBuild` so the output can access node_modules when we import
 * the output files. A hardcoded fallback dir is fine as it would be cleaned up after build.
 */
export declare function getOutDirWithinCwd(outDir: URL): URL;
