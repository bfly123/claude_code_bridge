import type { ComponentInstance, Params, Props, RouteData } from '../../@types/astro.js';
import type { Logger } from '../logger/core.js';
import type { RouteCache } from './route-cache.js';
interface GetParamsAndPropsOptions {
    mod: ComponentInstance | undefined;
    routeData?: RouteData | undefined;
    routeCache: RouteCache;
    pathname: string;
    logger: Logger;
    serverLike: boolean;
}
export declare function getProps(opts: GetParamsAndPropsOptions): Promise<Props>;
/**
 * When given a route with the pattern `/[x]/[y]/[z]/svelte`, and a pathname `/a/b/c/svelte`,
 * returns the params object: { x: "a", y: "b", z: "c" }.
 */
export declare function getParams(route: RouteData, pathname: string): Params;
export {};
