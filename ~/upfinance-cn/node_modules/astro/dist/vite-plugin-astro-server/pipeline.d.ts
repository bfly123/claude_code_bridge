import type { AstroSettings, ComponentInstance, ManifestData, RewritePayload, RouteData, SSRLoadedRenderer, SSRManifest } from '../@types/astro.js';
import type { HeadElements, TryRewriteResult } from '../core/base-pipeline.js';
import type { Logger } from '../core/logger/core.js';
import type { ModuleLoader } from '../core/module-loader/index.js';
import { Pipeline } from '../core/render/index.js';
export declare class DevPipeline extends Pipeline {
    readonly loader: ModuleLoader;
    readonly logger: Logger;
    readonly manifest: SSRManifest;
    readonly settings: AstroSettings;
    readonly config: import("../@types/astro.js").AstroConfig;
    readonly defaultRoutes: {
        instance: ComponentInstance;
        matchesComponent(filePath: URL): boolean;
        route: string;
        component: string;
    }[];
    renderers: SSRLoadedRenderer[];
    manifestData: ManifestData | undefined;
    componentInterner: WeakMap<RouteData, ComponentInstance>;
    private constructor();
    static create(manifestData: ManifestData, { loader, logger, manifest, settings, }: Pick<DevPipeline, 'loader' | 'logger' | 'manifest' | 'settings'>): DevPipeline;
    headElements(routeData: RouteData): Promise<HeadElements>;
    componentMetadata(routeData: RouteData): Promise<Map<string, import("../@types/astro.js").SSRComponentMetadata>>;
    preload(routeData: RouteData, filePath: URL): Promise<ComponentInstance>;
    clearRouteCache(): void;
    getComponentByRoute(routeData: RouteData): Promise<ComponentInstance>;
    tryRewrite(payload: RewritePayload, request: Request): Promise<TryRewriteResult>;
    setManifestData(manifestData: ManifestData): void;
    rewriteKnownRoute(route: string, sourceRoute: RouteData): ComponentInstance;
}
