import nodeFs from 'node:fs';
import type { Plugin } from 'vite';
import type { AstroSettings } from '../@types/astro.js';
import { type ContentLookupMap } from './utils.js';
interface AstroContentVirtualModPluginParams {
    settings: AstroSettings;
    fs: typeof nodeFs;
}
export declare function astroContentVirtualModPlugin({ settings, fs, }: AstroContentVirtualModPluginParams): Plugin;
export declare function generateContentEntryFile({ settings, lookupMap, IS_DEV, IS_SERVER, isClient, }: {
    settings: AstroSettings;
    fs: typeof nodeFs;
    lookupMap: ContentLookupMap;
    IS_DEV: boolean;
    IS_SERVER: boolean;
    isClient: boolean;
}): Promise<string>;
/**
 * Generate a map from a collection + slug to the local file path.
 * This is used internally to resolve entry imports when using `getEntry()`.
 * @see `templates/content/module.mjs`
 */
export declare function generateLookupMap({ settings, fs, }: {
    settings: AstroSettings;
    fs: typeof nodeFs;
}): Promise<ContentLookupMap>;
export {};
