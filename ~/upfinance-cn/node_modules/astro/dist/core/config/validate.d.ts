import type { AstroConfig } from '../../@types/astro.js';
/** Turn raw config values into normalized values */
export declare function validateConfig(userConfig: any, root: string, cmd: string): Promise<AstroConfig>;
