interface InitOptions {
    defaultStrategy?: string;
    prefetchAll?: boolean;
}
/**
 * Initialize the prefetch script, only works once.
 *
 * @param defaultOpts Default options for prefetching if not already set by the user config.
 */
export declare function init(defaultOpts?: InitOptions): void;
export interface PrefetchOptions {
    /**
     * How the prefetch should prioritize the URL. (default `'link'`)
     * - `'link'`: use `<link rel="prefetch">`.
     * - `'fetch'`: use `fetch()`.
     *
     * @deprecated It is recommended to not use this option, and let prefetch use `'link'` whenever it's supported,
     * or otherwise fall back to `'fetch'`. `'link'` works better if the URL doesn't set an appropriate cache header,
     * as the browser will continue to cache it as long as it's used subsequently.
     */
    with?: 'link' | 'fetch';
    /**
     * Should prefetch even on data saver mode or slow connection. (default `false`)
     */
    ignoreSlowConnection?: boolean;
}
/**
 * Prefetch a URL so it's cached when the user navigates to it.
 *
 * @param url A full or partial URL string based on the current `location.href`. They are only fetched if:
 *   - The user is online
 *   - The user is not in data saver mode
 *   - The URL is within the same origin
 *   - The URL is not the current page
 *   - The URL has not already been prefetched
 * @param opts Additional options for prefetching.
 */
export declare function prefetch(url: string, opts?: PrefetchOptions): void;
export {};
