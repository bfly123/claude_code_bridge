import type { imageType } from './types/index.js';
import type { ISizeCalculationResult } from './types/interface.ts';
/**
 * Return size information based on an Uint8Array
 *
 * @param {Uint8Array} input
 * @returns {ISizeCalculationResult}
 */
export declare function lookup(input: Uint8Array): ISizeCalculationResult;
export declare const disableTypes: (types: imageType[]) => void;
