import type { AstroConfig, RouteData, SerializedRouteData } from '../../../@types/astro.js';
export declare function serializeRouteData(routeData: RouteData, trailingSlash: AstroConfig['trailingSlash']): SerializedRouteData;
export declare function deserializeRouteData(rawRouteData: SerializedRouteData): RouteData;
