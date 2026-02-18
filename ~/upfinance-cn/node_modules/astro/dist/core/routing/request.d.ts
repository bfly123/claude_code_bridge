/**
 * Utilities for extracting information from `Request`
 */
export declare function getFirstForwardedValue(multiValueHeader?: string | string[] | null): string | undefined;
/**
 * Returns the first value associated to the `x-forwarded-for` header.
 *
 * @param {Request} request
 */
export declare function getClientIpAddress(request: Request): string | undefined;
