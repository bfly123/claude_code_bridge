import type { ManifestData, RouteData, SSRManifest } from '../../@types/astro.js';
import { getSetCookiesFromResponse } from '../cookies/index.js';
import { AstroIntegrationLogger } from '../logger/core.js';
export { deserializeManifest } from './common.js';
export interface RenderOptions {
    /**
     * Whether to automatically add all cookies written by `Astro.cookie.set()` to the response headers.
     *
     * When set to `true`, they will be added to the `Set-Cookie` header as comma-separated key=value pairs. You can use the standard `response.headers.getSetCookie()` API to read them individually.
     *
     * When set to `false`, the cookies will only be available from `App.getSetCookieFromResponse(response)`.
     *
     * @default {false}
     */
    addCookieHeader?: boolean;
    /**
     * The client IP address that will be made available as `Astro.clientAddress` in pages, and as `ctx.clientAddress` in API routes and middleware.
     *
     * Default: `request[Symbol.for("astro.clientAddress")]`
     */
    clientAddress?: string;
    /**
     * The mutable object that will be made available as `Astro.locals` in pages, and as `ctx.locals` in API routes and middleware.
     */
    locals?: object;
    /**
     * **Advanced API**: you probably do not need to use this.
     *
     * Default: `app.match(request)`
     */
    routeData?: RouteData;
}
export interface RenderErrorOptions {
    locals?: App.Locals;
    routeData?: RouteData;
    response?: Response;
    status: 404 | 500;
    /**
     * Whether to skip middleware while rendering the error page. Defaults to false.
     */
    skipMiddleware?: boolean;
    /**
     * Allows passing an error to 500.astro. It will be available through `Astro.props.error`.
     */
    error?: unknown;
}
export declare class App {
    #private;
    constructor(manifest: SSRManifest, streaming?: boolean);
    getAdapterLogger(): AstroIntegrationLogger;
    set setManifestData(newManifestData: ManifestData);
    removeBase(pathname: string): string;
    match(request: Request): RouteData | undefined;
    render(request: Request, options?: RenderOptions): Promise<Response>;
    /**
     * @deprecated Instead of passing `RouteData` and locals individually, pass an object with `routeData` and `locals` properties.
     * See https://github.com/withastro/astro/pull/9199 for more information.
     */
    render(request: Request, routeData?: RouteData, locals?: object): Promise<Response>;
    setCookieHeaders(response: Response): Generator<string, string[], any>;
    /**
     * Reads all the cookies written by `Astro.cookie.set()` onto the passed response.
     * For example,
     * ```ts
     * for (const cookie_ of App.getSetCookieFromResponse(response)) {
     *     const cookie: string = cookie_
     * }
     * ```
     * @param response The response to read cookies from.
     * @returns An iterator that yields key-value pairs as equal-sign-separated strings.
     */
    static getSetCookieFromResponse: typeof getSetCookiesFromResponse;
}
