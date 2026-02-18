import type { AstroInlineConfig } from '../../@types/astro.js';
export interface BuildOptions {
}
/**
 * Builds your site for deployment. By default, this will generate static files and place them in a dist/ directory.
 * If SSR is enabled, this will generate the necessary server files to serve your site.
 *
 * @experimental The JavaScript API is experimental
 */
export default function build(inlineConfig: AstroInlineConfig, options?: BuildOptions): Promise<void>;
