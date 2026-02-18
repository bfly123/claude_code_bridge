import type { BuildInternals } from '../internal.js';
import type { AstroBuildPlugin } from '../plugin.js';
import type { StaticBuildOptions } from '../types.js';
export declare const SSR_VIRTUAL_MODULE_ID = "@astrojs-ssr-virtual-entry";
export declare const RESOLVED_SSR_VIRTUAL_MODULE_ID: string;
export declare function pluginSSR(options: StaticBuildOptions, internals: BuildInternals): AstroBuildPlugin;
export declare const SPLIT_MODULE_ID = "@astro-page-split:";
export declare const RESOLVED_SPLIT_MODULE_ID = "\0@astro-page-split:";
export declare function pluginSSRSplit(options: StaticBuildOptions, internals: BuildInternals): AstroBuildPlugin;
