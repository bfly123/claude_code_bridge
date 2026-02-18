import type { ImageMetadata } from '../types.js';
export declare function getOrigQueryParams(params: URLSearchParams): Pick<ImageMetadata, 'width' | 'height' | 'format'> | undefined;
