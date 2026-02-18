import type { Plugin as VitePlugin } from 'vite';
import type { BuildInternals } from '../internal.js';
import type { AstroBuildPlugin } from '../plugin.js';
export declare const astroEntryPrefix = "\0astro-entry:";
/**
 * When adding hydrated or client:only components as Rollup inputs, sometimes we're not using all
 * of the export names, e.g. `import { Counter } from './ManyComponents.jsx'`. This plugin proxies
 * entries to re-export only the names the user is using.
 */
export declare function vitePluginComponentEntry(internals: BuildInternals): VitePlugin;
export declare function normalizeEntryId(id: string): string;
export declare function pluginComponentEntry(internals: BuildInternals): AstroBuildPlugin;
