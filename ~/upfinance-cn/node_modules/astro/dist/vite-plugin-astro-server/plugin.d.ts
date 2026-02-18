import type fs from 'node:fs';
import type * as vite from 'vite';
import type { AstroSettings, SSRManifest } from '../@types/astro.js';
import type { Logger } from '../core/logger/core.js';
export interface AstroPluginOptions {
    settings: AstroSettings;
    logger: Logger;
    fs: typeof fs;
}
export default function createVitePluginAstroServer({ settings, logger, fs: fsMod, }: AstroPluginOptions): vite.Plugin;
/**
 * It creates a `SSRManifest` from the `AstroSettings`.
 *
 * Renderers needs to be pulled out from the page module emitted during the build.
 * @param settings
 */
export declare function createDevelopmentManifest(settings: AstroSettings): SSRManifest;
