import type { SSRElement } from '../@types/astro.js';
import type { ModuleLoader } from '../core/module-loader/index.js';
export declare function getScriptsForURL(filePath: URL, root: URL, loader: ModuleLoader): Promise<{
    scripts: Set<SSRElement>;
    crawledFiles: Set<string>;
}>;
