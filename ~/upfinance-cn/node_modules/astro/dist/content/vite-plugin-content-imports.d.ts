import type fsMod from 'node:fs';
import type { Plugin } from 'vite';
import type { AstroSettings } from '../@types/astro.js';
import type { Logger } from '../core/logger/core.js';
export declare function astroContentImportPlugin({ fs, settings, logger, }: {
    fs: typeof fsMod;
    settings: AstroSettings;
    logger: Logger;
}): Plugin[];
