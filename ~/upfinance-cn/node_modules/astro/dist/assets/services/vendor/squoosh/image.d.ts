import type { ImageOutputFormat } from '../../../types.js';
type RotateOperation = {
    type: 'rotate';
    numRotations: number;
};
type ResizeOperation = {
    type: 'resize';
    width?: number;
    height?: number;
};
export type Operation = RotateOperation | ResizeOperation;
export declare function processBuffer(buffer: Buffer, operations: Operation[], encoding: ImageOutputFormat, quality?: number): Promise<Uint8Array>;
export {};
