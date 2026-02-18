import type { Plugin as VitePlugin } from 'vite';
import type { BuildInternals } from '../internal.js';
import type { AstroBuildPlugin } from '../plugin.js';
export declare function vitePluginInternals(input: Set<string>, internals: BuildInternals): VitePlugin;
export declare function pluginInternals(internals: BuildInternals): AstroBuildPlugin;
