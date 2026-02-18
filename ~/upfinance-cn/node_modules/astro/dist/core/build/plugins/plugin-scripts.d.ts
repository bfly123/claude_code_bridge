import type { Plugin as VitePlugin } from 'vite';
import type { BuildInternals } from '../internal.js';
import type { AstroBuildPlugin } from '../plugin.js';
/**
 * Used by the `experimental.directRenderScript` option to inline scripts directly into the HTML.
 */
export declare function vitePluginScripts(internals: BuildInternals): VitePlugin;
export declare function pluginScripts(internals: BuildInternals): AstroBuildPlugin;
