import type { ImageMetadata } from '../types.js';
export declare function imageMetadata(data: Uint8Array, src?: string): Promise<Omit<ImageMetadata, 'src' | 'fsPath'>>;
