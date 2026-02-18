import type * as vite from 'vite';
import type { AstroSettings } from '../@types/astro.js';
import type { Logger } from '../core/logger/core.js';
export declare function baseMiddleware(settings: AstroSettings, logger: Logger): vite.Connect.NextHandleFunction;
