import type { Loader } from './types.js';
/**
 * Loads entries from a JSON file. The file must contain an array of objects that contain unique `id` fields, or an object with string keys.
 * @todo Add support for other file types, such as YAML, CSV etc.
 * @param fileName The path to the JSON file to load, relative to the content directory.
 */
export declare function file(fileName: string): Loader;
