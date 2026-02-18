import type { Plugin as VitePlugin } from 'vite';
import type { AstroSettings } from '../@types/astro.js';
import type { Logger } from '../core/logger/core.js';
export interface AstroPluginScannerOptions {
    settings: AstroSettings;
    logger: Logger;
}
export default function astroScannerPlugin({ settings, logger, }: AstroPluginScannerOptions): VitePlugin;
