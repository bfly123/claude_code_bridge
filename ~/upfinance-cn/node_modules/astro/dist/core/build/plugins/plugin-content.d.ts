import type { BuildInternals } from '../internal.js';
import type { AstroBuildPlugin } from '../plugin.js';
import type { StaticBuildOptions } from '../types.js';
export declare function copyContentToCache(opts: StaticBuildOptions): Promise<string[]>;
export declare function pluginContent(opts: StaticBuildOptions, internals: BuildInternals): AstroBuildPlugin;
