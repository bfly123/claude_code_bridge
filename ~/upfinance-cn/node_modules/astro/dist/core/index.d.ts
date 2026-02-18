import type { AstroInlineConfig } from '../@types/astro.js';
export { default as dev } from './dev/index.js';
export { default as preview } from './preview/index.js';
/**
 * Builds your site for deployment. By default, this will generate static files and place them in a dist/ directory.
 * If SSR is enabled, this will generate the necessary server files to serve your site.
 *
 * @experimental The JavaScript API is experimental
 */
export declare const build: (inlineConfig: AstroInlineConfig) => Promise<void>;
/**
 * Generates TypeScript types for all Astro modules. This sets up a `src/env.d.ts` file for type inferencing,
 * and defines the `astro:content` module for the Content Collections API.
 *
 * @experimental The JavaScript API is experimental
 */
export declare const sync: (inlineConfig: AstroInlineConfig) => Promise<void>;
