import type fsMod from 'node:fs';
import type { AstroSettings } from '../../@types/astro.js';
import type { Logger } from '../logger/core.js';
export declare function writeFiles(settings: AstroSettings, fs: typeof fsMod, logger: Logger): Promise<void>;
