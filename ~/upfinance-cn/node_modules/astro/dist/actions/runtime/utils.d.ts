import type { APIContext } from '../../@types/astro.js';
export declare const ACTION_API_CONTEXT_SYMBOL: unique symbol;
export declare const formContentTypes: string[];
export declare function hasContentType(contentType: string, expected: string[]): boolean;
export type ActionAPIContext = Omit<APIContext, 'getActionResult' | 'callAction' | 'props' | 'redirect'>;
export type MaybePromise<T> = T | Promise<T>;
/**
 * Used to preserve the input schema type in the error object.
 * This allows for type inference on the `fields` property
 * when type narrowed to an `ActionInputError`.
 *
 * Example: Action has an input schema of `{ name: z.string() }`.
 * When calling the action and checking `isInputError(result.error)`,
 * `result.error.fields` will be typed with the `name` field.
 */
export type ErrorInferenceObject = Record<string, any>;
export declare function isActionAPIContext(ctx: ActionAPIContext): boolean;
