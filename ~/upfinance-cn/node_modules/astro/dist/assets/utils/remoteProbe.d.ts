import type { ImageMetadata } from '../types.js';
export declare function inferRemoteSize(url: string): Promise<Omit<ImageMetadata, 'src' | 'fsPath'>>;
