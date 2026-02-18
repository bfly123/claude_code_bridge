import type { RouteData } from '../../@types/astro.js';
import { type BuildInternals } from '../../core/build/internal.js';
import type { StaticBuildOptions } from './types.js';
export declare function viteBuild(opts: StaticBuildOptions): Promise<{
    internals: BuildInternals;
    ssrOutputChunkNames: string[];
}>;
export declare function staticBuild(opts: StaticBuildOptions, internals: BuildInternals, ssrOutputChunkNames: string[]): Promise<void>;
export declare function copyFiles(fromFolder: URL, toFolder: URL, includeDotfiles?: boolean): Promise<void[] | undefined>;
/**
 * This function takes the virtual module name of any page entrypoint and
 * transforms it to generate a final `.mjs` output file.
 *
 * Input: `@astro-page:src/pages/index@_@astro`
 * Output: `pages/index.astro.mjs`
 * Input: `@astro-page:../node_modules/my-dep/injected@_@astro`
 * Output: `pages/injected.mjs`
 *
 * 1. We clean the `facadeModuleId` by removing the `ASTRO_PAGE_MODULE_ID` prefix and `ASTRO_PAGE_EXTENSION_POST_PATTERN`.
 * 2. We find the matching route pattern in the manifest (or fallback to the cleaned module id)
 * 3. We replace square brackets with underscore (`[slug]` => `_slug_`) and `...` with `` (`[...slug]` => `_---slug_`).
 * 4. We append the `.mjs` extension, so the file will always be an ESM module
 *
 * @param prefix string
 * @param facadeModuleId string
 * @param pages AllPagesData
 */
export declare function makeAstroPageEntryPointFileName(prefix: string, facadeModuleId: string, routes: RouteData[]): string;
/**
 * The `facadeModuleId` has a shape like: \0@astro-serverless-page:src/pages/index@_@astro.
 *
 * 1. We call `makeAstroPageEntryPointFileName` which normalise its name, making it like a file path
 * 2. We split the file path using the file system separator and attempt to retrieve the last entry
 * 3. The last entry should be the file
 * 4. We prepend the file name with `entry.`
 * 5. We built the file path again, using the new en3built in the previous step
 *
 * @param facadeModuleId
 * @param opts
 */
export declare function makeSplitEntryPointFileName(facadeModuleId: string, routes: RouteData[]): string;
