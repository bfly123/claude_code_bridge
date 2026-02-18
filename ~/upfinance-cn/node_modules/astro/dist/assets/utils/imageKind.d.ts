import type { ImageMetadata, UnresolvedImageTransform } from '../types.js';
export declare function isESMImportedImage(src: ImageMetadata | string): src is ImageMetadata;
export declare function isRemoteImage(src: ImageMetadata | string): src is string;
export declare function resolveSrc(src: UnresolvedImageTransform['src']): Promise<string | ImageMetadata>;
