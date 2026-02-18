import type { SSRElement } from '../../../@types/astro.js';
import type { RenderFunction } from './common.js';
export declare const voidElementNames: RegExp;
export declare const toAttributeString: (value: any, shouldEscape?: boolean) => any;
export declare function defineScriptVars(vars: Record<any, any>): any;
export declare function formatList(values: string[]): string;
export declare function addAttribute(value: any, key: string, shouldEscape?: boolean): any;
export declare function internalSpreadAttributes(values: Record<any, any>, shouldEscape?: boolean): any;
export declare function renderElement(name: string, { props: _props, children }: SSRElement, shouldEscape?: boolean): string;
/**
 * Executes the `bufferRenderFunction` to prerender it into a buffer destination, and return a promise
 * with an object containing the `renderToFinalDestination` function to flush the buffer to the final
 * destination.
 *
 * @example
 * ```ts
 * // Render components in parallel ahead of time
 * const finalRenders = [ComponentA, ComponentB].map((comp) => {
 *   return renderToBufferDestination(async (bufferDestination) => {
 *     await renderComponentToDestination(bufferDestination);
 *   });
 * });
 * // Render array of components serially
 * for (const finalRender of finalRenders) {
 *   await finalRender.renderToFinalDestination(finalDestination);
 * }
 * ```
 */
export declare function renderToBufferDestination(bufferRenderFunction: RenderFunction): {
    renderToFinalDestination: RenderFunction;
};
export declare const isNode: boolean;
export declare const isDeno: boolean;
export type PromiseWithResolvers<T> = {
    promise: Promise<T>;
    resolve: (value: T) => void;
    reject: (reason?: any) => void;
};
export declare function promiseWithResolvers<T = any>(): PromiseWithResolvers<T>;
