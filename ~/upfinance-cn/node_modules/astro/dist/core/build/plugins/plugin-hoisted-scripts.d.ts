import type { Plugin as VitePlugin } from 'vite';
import type { BuildInternals } from '../internal.js';
import type { AstroBuildPlugin } from '../plugin.js';
export declare function vitePluginHoistedScripts(internals: BuildInternals): VitePlugin;
export declare function pluginHoistedScripts(internals: BuildInternals): AstroBuildPlugin;
