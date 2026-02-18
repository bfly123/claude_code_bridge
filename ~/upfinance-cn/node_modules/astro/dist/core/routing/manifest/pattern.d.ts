import type { AstroConfig, RoutePart } from '../../../@types/astro.js';
export declare function getPattern(segments: RoutePart[][], base: AstroConfig['base'], addTrailingSlash: AstroConfig['trailingSlash']): RegExp;
