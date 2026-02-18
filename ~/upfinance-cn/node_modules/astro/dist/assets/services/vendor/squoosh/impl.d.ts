import ImageData from './image_data.js';
export declare function decodeBuffer(_buffer: Buffer | Uint8Array): Promise<ImageData>;
export declare function rotate(image: ImageData, numRotations: number): Promise<ImageData>;
type ResizeOpts = {
    image: ImageData;
} & {
    width?: number;
    height?: number;
};
export declare function resize({ image, width, height }: ResizeOpts): Promise<ImageData>;
export declare function encodeJpeg(image: ImageData, opts: {
    quality?: number;
}): Promise<Uint8Array>;
export declare function encodeWebp(image: ImageData, opts: {
    quality?: number;
}): Promise<Uint8Array>;
export declare function encodeAvif(image: ImageData, opts: {
    quality?: number;
}): Promise<Uint8Array>;
export declare function encodePng(image: ImageData): Promise<Uint8Array>;
export {};
