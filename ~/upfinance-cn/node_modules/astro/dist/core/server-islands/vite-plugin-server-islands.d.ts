import type { Plugin as VitePlugin } from 'vite';
import type { AstroSettings } from '../../@types/astro.js';
export declare const VIRTUAL_ISLAND_MAP_ID = "@astro-server-islands";
export declare const RESOLVED_VIRTUAL_ISLAND_MAP_ID: string;
export declare function vitePluginServerIslands({ settings }: {
    settings: AstroSettings;
}): VitePlugin;
