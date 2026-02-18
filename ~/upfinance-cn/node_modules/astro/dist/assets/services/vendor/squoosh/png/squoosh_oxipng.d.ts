/**
 * @param {Uint8Array} data
 * @param {number} level
 * @param {boolean} interlace
 * @returns {Uint8Array}
 */
export declare function optimise(data: any, level: any, interlace: any): any;
declare function init(input: any): Promise<WebAssembly.Exports>;
export default init;
export declare function cleanup(): void;
