import type { ComponentInstance, ManifestData, RouteData, SSRManifest } from '../../@types/astro.js';
export declare const SERVER_ISLAND_ROUTE = "/_server-islands/[name]";
export declare const SERVER_ISLAND_COMPONENT = "_server-islands.astro";
type ConfigFields = Pick<SSRManifest, 'base' | 'trailingSlash'>;
export declare function getServerIslandRouteData(config: ConfigFields): RouteData;
export declare function ensureServerIslandRoute(config: ConfigFields, routeManifest: ManifestData): void;
export declare function createEndpoint(manifest: SSRManifest): ComponentInstance;
export {};
