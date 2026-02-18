import type { AstroSettings } from '../@types/astro.js';
import type { PageOptions } from '../vite-plugin-astro/types.js';
export declare function scan(code: string, id: string, settings?: AstroSettings): Promise<PageOptions>;
