import type * as vite from 'vite';
import type { AstroBuildPlugin } from '../core/build/plugin.js';
import type { BuildInternals } from '../core/build/internal.js';
export default function configHeadVitePlugin(): vite.Plugin;
export declare function astroHeadBuildPlugin(internals: BuildInternals): AstroBuildPlugin;
