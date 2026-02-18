import type { Plugin } from 'vite';
import type { AstroSettings } from '../@types/astro.js';
import type { BuildInternals } from '../core/build/internal.js';
import type { AstroBuildPlugin } from '../core/build/plugin.js';
import type { StaticBuildOptions } from '../core/build/types.js';
export declare function astroContentAssetPropagationPlugin({ mode, settings, }: {
    mode: string;
    settings: AstroSettings;
}): Plugin;
export declare function astroConfigBuildPlugin(options: StaticBuildOptions, internals: BuildInternals): AstroBuildPlugin;
