import type { ComponentInstance, MiddlewareHandler, RewritePayload, RouteData, RuntimeMode, SSRLoadedRenderer, SSRManifest, SSRResult } from '../@types/astro.js';
import type { Logger } from './logger/core.js';
import { RouteCache } from './render/route-cache.js';
/**
 * The `Pipeline` represents the static parts of rendering that do not change between requests.
 * These are mostly known when the server first starts up and do not change.
 *
 * Thus, a `Pipeline` is created once at process start and then used by every `RenderContext`.
 */
export declare abstract class Pipeline {
    readonly logger: Logger;
    readonly manifest: SSRManifest;
    /**
     * "development" or "production"
     */
    readonly mode: RuntimeMode;
    readonly renderers: SSRLoadedRenderer[];
    readonly resolve: (s: string) => Promise<string>;
    /**
     * Based on Astro config's `output` option, `true` if "server" or "hybrid".
     */
    readonly serverLike: boolean;
    readonly streaming: boolean;
    /**
     * Used to provide better error messages for `Astro.clientAddress`
     */
    readonly adapterName: string;
    readonly clientDirectives: Map<string, string>;
    readonly inlinedScripts: Map<string, string>;
    readonly compressHTML: boolean;
    readonly i18n: import("./app/types.js").SSRManifestI18n | undefined;
    readonly middleware: (() => Promise<import("../@types/astro.js").AstroMiddlewareInstance> | import("../@types/astro.js").AstroMiddlewareInstance) | undefined;
    readonly routeCache: RouteCache;
    /**
     * Used for `Astro.site`.
     */
    readonly site: URL | undefined;
    /**
     * Array of built-in, internal, routes.
     * Used to find the route module
     */
    readonly defaultRoutes: {
        instance: ComponentInstance;
        matchesComponent(filePath: URL): boolean;
        route: string;
        component: string;
    }[];
    readonly internalMiddleware: MiddlewareHandler[];
    resolvedMiddleware: MiddlewareHandler | undefined;
    constructor(logger: Logger, manifest: SSRManifest, 
    /**
     * "development" or "production"
     */
    mode: RuntimeMode, renderers: SSRLoadedRenderer[], resolve: (s: string) => Promise<string>, 
    /**
     * Based on Astro config's `output` option, `true` if "server" or "hybrid".
     */
    serverLike: boolean, streaming: boolean, 
    /**
     * Used to provide better error messages for `Astro.clientAddress`
     */
    adapterName?: string, clientDirectives?: Map<string, string>, inlinedScripts?: Map<string, string>, compressHTML?: boolean, i18n?: import("./app/types.js").SSRManifestI18n | undefined, middleware?: (() => Promise<import("../@types/astro.js").AstroMiddlewareInstance> | import("../@types/astro.js").AstroMiddlewareInstance) | undefined, routeCache?: RouteCache, 
    /**
     * Used for `Astro.site`.
     */
    site?: URL | undefined, 
    /**
     * Array of built-in, internal, routes.
     * Used to find the route module
     */
    defaultRoutes?: {
        instance: ComponentInstance;
        matchesComponent(filePath: URL): boolean;
        route: string;
        component: string;
    }[]);
    abstract headElements(routeData: RouteData): Promise<HeadElements> | HeadElements;
    abstract componentMetadata(routeData: RouteData): Promise<SSRResult['componentMetadata']> | void;
    /**
     * It attempts to retrieve the `RouteData` that matches the input `url`, and the component that belongs to the `RouteData`.
     *
     * ## Errors
     *
     * - if not `RouteData` is found
     *
     * @param {RewritePayload} rewritePayload The payload provided by the user
     * @param {Request} request The original request
     */
    abstract tryRewrite(rewritePayload: RewritePayload, request: Request): Promise<TryRewriteResult>;
    /**
     * Tells the pipeline how to retrieve a component give a `RouteData`
     * @param routeData
     */
    abstract getComponentByRoute(routeData: RouteData): Promise<ComponentInstance>;
    /**
     * Resolves the middleware from the manifest, and returns the `onRequest` function. If `onRequest` isn't there,
     * it returns a no-op function
     */
    getMiddleware(): Promise<MiddlewareHandler>;
}
export interface HeadElements extends Pick<SSRResult, 'scripts' | 'styles' | 'links'> {
}
export interface TryRewriteResult {
    routeData: RouteData;
    componentInstance: ComponentInstance;
    newUrl: URL;
    pathname: string;
}
