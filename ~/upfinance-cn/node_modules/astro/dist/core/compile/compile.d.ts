import type { TransformResult } from '@astrojs/compiler';
import type { ResolvedConfig } from 'vite';
import type { AstroConfig } from '../../@types/astro.js';
import type { AstroPreferences } from '../../preferences/index.js';
import type { CompileCssResult } from './types.js';
export interface CompileProps {
    astroConfig: AstroConfig;
    viteConfig: ResolvedConfig;
    preferences: AstroPreferences;
    filename: string;
    source: string;
}
export interface CompileResult extends Omit<TransformResult, 'css'> {
    css: CompileCssResult[];
}
export declare function compile({ astroConfig, viteConfig, preferences, filename, source, }: CompileProps): Promise<CompileResult>;
