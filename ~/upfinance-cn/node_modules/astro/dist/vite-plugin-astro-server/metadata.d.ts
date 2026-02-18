import type { SSRResult } from '../@types/astro.js';
import type { ModuleLoader } from '../core/module-loader/index.js';
export declare function getComponentMetadata(filePath: URL, loader: ModuleLoader): Promise<SSRResult['componentMetadata']>;
