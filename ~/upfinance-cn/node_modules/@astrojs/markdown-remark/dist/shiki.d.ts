import type { ShikiConfig } from './types.js';
export interface ShikiHighlighter {
    highlight(code: string, lang?: string, options?: {
        inline?: boolean;
        attributes?: Record<string, string>;
        /**
         * Raw `meta` information to be used by Shiki transformers
         */
        meta?: string;
    }): Promise<string>;
}
export declare function createShikiHighlighter({ langs, theme, themes, defaultColor, wrap, transformers, langAlias, }?: ShikiConfig): Promise<ShikiHighlighter>;
