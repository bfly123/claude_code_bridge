import type * as vite from 'vite';
import type { AstroSettings } from '../@types/astro.js';
import type { Logger } from '../core/logger/core.js';
interface EnvPluginOptions {
    settings: AstroSettings;
    logger: Logger;
}
export default function envVitePlugin({ settings, logger }: EnvPluginOptions): vite.Plugin;
export {};
