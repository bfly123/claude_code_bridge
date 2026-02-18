import type { AstroConfig, AstroSettings } from '../../@types/astro.js';
export declare function createBaseSettings(config: AstroConfig): AstroSettings;
export declare function createSettings(config: AstroConfig, cwd?: string): Promise<AstroSettings>;
