import type { MiddlewareHandler } from '../../@types/astro.js';
/**
 * Returns a middleware function in charge to check the `origin` header.
 *
 * @private
 */
export declare function createOriginCheckMiddleware(): MiddlewareHandler;
