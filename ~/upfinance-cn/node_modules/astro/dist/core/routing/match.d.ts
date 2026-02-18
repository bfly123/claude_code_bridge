import type { ManifestData, RouteData } from '../../@types/astro.js';
/** Find matching route from pathname */
export declare function matchRoute(pathname: string, manifest: ManifestData): RouteData | undefined;
/** Finds all matching routes from pathname */
export declare function matchAllRoutes(pathname: string, manifest: ManifestData): RouteData[];
/**
 * Determines if the given route matches a 404 or 500 error page.
 *
 * @param {RouteData} route - The route data to check.
 * @returns {boolean} `true` if the route matches a 404 or 500 error page, otherwise `false`.
 */
export declare function isRoute404or500(route: RouteData): boolean;
