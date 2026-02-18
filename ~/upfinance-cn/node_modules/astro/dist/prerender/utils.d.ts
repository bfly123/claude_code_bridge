import type { AstroConfig } from '../@types/astro.js';
export declare function getPrerenderDefault(config: AstroConfig): boolean;
/**
 * Returns the correct output directory of the SSR build based on the configuration
 */
export declare function getOutputDirectory(config: AstroConfig): URL;
