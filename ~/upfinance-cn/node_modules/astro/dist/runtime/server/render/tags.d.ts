import type { SSRElement, SSRResult } from '../../../@types/astro.js';
import type { StylesheetAsset } from '../../../core/app/types.js';
export declare function renderScriptElement({ props, children }: SSRElement): string;
export declare function renderUniqueStylesheet(result: SSRResult, sheet: StylesheetAsset): string | undefined;
