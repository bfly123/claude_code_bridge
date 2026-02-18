/**
 * @param {Uint8Array} data
 * @param {number} width
 * @param {number} height
 * @returns {Uint8Array}
 */
export declare function encode(data: any, width: any, height: any): any;
/**
 * @param {Uint8Array} data
 * @returns {ImageData}
 */
export declare function decode(data: any): any;
declare function init(input: any): Promise<WebAssembly.Exports>;
export default init;
export declare function cleanup(): void;
