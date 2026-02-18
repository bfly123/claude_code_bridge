import type { ImageOutputFormat } from '../../../types.js';
import type { Operation } from './image.js';
export declare function processBuffer(buffer: Uint8Array, operations: Operation[], encoding: ImageOutputFormat, quality?: number): Promise<Uint8Array>;
