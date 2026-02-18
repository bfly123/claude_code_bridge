import type fsMod from 'node:fs';
import type { Plugin as VitePlugin } from 'vite';
import type { AstroSettings } from '../@types/astro.js';
/**
 * This plugin is responsible to load the known file `actions/index.js` / `actions.js`
 * If the file doesn't exist, it returns an empty object.
 * @param settings
 */
export declare function vitePluginUserActions({ settings }: {
    settings: AstroSettings;
}): VitePlugin;
export declare function vitePluginActions({ fs, settings, }: {
    fs: typeof fsMod;
    settings: AstroSettings;
}): VitePlugin;
