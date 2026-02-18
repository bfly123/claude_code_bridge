import type * as vite from 'vite';
import type { AstroSettings } from '../@types/astro.js';
import type { Logger } from '../core/logger/core.js';
import type { PluginCssMetadata as AstroPluginCssMetadata, PluginMetadata as AstroPluginMetadata } from './types.js';
export { getAstroMetadata } from './metadata.js';
export type { AstroPluginMetadata, AstroPluginCssMetadata };
interface AstroPluginOptions {
    settings: AstroSettings;
    logger: Logger;
}
/** Transform .astro files for Vite */
export default function astro({ settings, logger }: AstroPluginOptions): vite.Plugin[];
