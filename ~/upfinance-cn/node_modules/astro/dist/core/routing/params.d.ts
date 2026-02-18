import type { GetStaticPathsItem, RouteData } from '../../@types/astro.js';
/**
 * given a route's Params object, validate parameter
 * values and create a stringified key for the route
 * that can be used to match request routes
 */
export declare function stringifyParams(params: GetStaticPathsItem['params'], route: RouteData): string;
