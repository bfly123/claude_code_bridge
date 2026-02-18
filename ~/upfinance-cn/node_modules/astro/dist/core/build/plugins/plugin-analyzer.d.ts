import type { Plugin as VitePlugin } from 'vite';
import type { BuildInternals } from '../internal.js';
import type { AstroBuildPlugin } from '../plugin.js';
import type { StaticBuildOptions } from '../types.js';
export declare function vitePluginAnalyzer(options: StaticBuildOptions, internals: BuildInternals): VitePlugin;
export declare function pluginAnalyzer(options: StaticBuildOptions, internals: BuildInternals): AstroBuildPlugin;
