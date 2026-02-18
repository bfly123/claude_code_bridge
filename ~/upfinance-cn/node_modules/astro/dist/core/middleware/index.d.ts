import type { APIContext, MiddlewareHandler, Params } from '../../@types/astro.js';
import { sequence } from './sequence.js';
declare function defineMiddleware(fn: MiddlewareHandler): MiddlewareHandler;
/**
 * Payload for creating a context to be passed to Astro middleware
 */
export type CreateContext = {
    /**
     * The incoming request
     */
    request: Request;
    /**
     * Optional parameters
     */
    params?: Params;
    /**
     * A list of locales that are supported by the user
     */
    userDefinedLocales?: string[];
    /**
     * User defined default locale
     */
    defaultLocale: string;
};
/**
 * Creates a context to be passed to Astro middleware `onRequest` function.
 */
declare function createContext({ request, params, userDefinedLocales, defaultLocale, }: CreateContext): APIContext;
/**
 * It attempts to serialize `value` and return it as a string.
 *
 * ## Errors
 *  If the `value` is not serializable if the function will throw a runtime error.
 *
 * Something is **not serializable** when it contains properties/values like functions, `Map`, `Set`, `Date`,
 * and other types that can't be made a string.
 *
 * @param value
 */
declare function trySerializeLocals(value: unknown): string;
export { createContext, defineMiddleware, sequence, trySerializeLocals };
