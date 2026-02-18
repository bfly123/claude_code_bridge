import type { ComponentInstance, ManifestData, SSRManifest } from '../../@types/astro.js';
export declare function injectDefaultRoutes(ssrManifest: SSRManifest, routeManifest: ManifestData): ManifestData;
type DefaultRouteParams = {
    instance: ComponentInstance;
    matchesComponent(filePath: URL): boolean;
    route: string;
    component: string;
};
export declare function createDefaultRoutes(manifest: SSRManifest): DefaultRouteParams[];
export {};
