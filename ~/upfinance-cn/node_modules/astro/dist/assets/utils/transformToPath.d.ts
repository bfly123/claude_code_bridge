import type { ImageTransform } from '../types.js';
export declare function propsToFilename(filePath: string, transform: ImageTransform, hash: string): string;
export declare function hashTransform(transform: ImageTransform, imageService: string, propertiesToHash: string[]): string;
