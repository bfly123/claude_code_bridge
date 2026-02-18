/**
 * @param {Uint8Array} input_image
 * @param {number} input_width
 * @param {number} input_height
 * @param {number} output_width
 * @param {number} output_height
 * @param {number} typ_idx
 * @param {boolean} premultiply
 * @param {boolean} color_space_conversion
 * @returns {Uint8ClampedArray}
 */
export declare function resize(input_image: any, input_width: any, input_height: any, output_width: any, output_height: any, typ_idx: any, premultiply: any, color_space_conversion: any): any;
declare function init(input: any): Promise<WebAssembly.Exports>;
export default init;
export declare function cleanup(): void;
