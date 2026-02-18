import type { SSRResult } from '../../../@types/astro.js';
/**
 * Relies on the `renderScript: true` compiler option
 * @experimental
 */
export declare function renderScript(result: SSRResult, id: string): Promise<any>;
