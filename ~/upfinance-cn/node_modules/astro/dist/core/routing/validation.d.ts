import type { ComponentInstance, GetStaticPathsResult, RouteData } from '../../@types/astro.js';
import type { Logger } from '../logger/core.js';
/** Throws error for invalid parameter in getStaticPaths() response */
export declare function validateGetStaticPathsParameter([key, value]: [string, any], route: string): void;
/** Error for deprecated or malformed route components */
export declare function validateDynamicRouteModule(mod: ComponentInstance, { ssr, route, }: {
    ssr: boolean;
    route: RouteData;
}): void;
/** Throw error and log warnings for malformed getStaticPaths() response */
export declare function validateGetStaticPathsResult(result: GetStaticPathsResult, logger: Logger, route: RouteData): void;
