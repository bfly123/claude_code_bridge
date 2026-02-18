import type { AstroRenderer, SSRLoadedRenderer } from '../@types/astro.js';
/**
 * Use this function to provide renderers to the `AstroContainer`:
 *
 * ```js
 * import { getContainerRenderer } from "@astrojs/react";
 * import { experimental_AstroContainer as AstroContainer } from "astro/container";
 * import { loadRenderers } from "astro:container"; // use this only when using vite/vitest
 *
 * const renderers = await loadRenderers([ getContainerRenderer ]);
 * const container = await AstroContainer.create({ renderers });
 *
 * ```
 * @param renderers
 */
export declare function loadRenderers(renderers: AstroRenderer[]): Promise<SSRLoadedRenderer[]>;
