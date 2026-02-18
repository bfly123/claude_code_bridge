export { createComponent } from './astro-component.js';
export { createAstro } from './astro-global.js';
export { renderEndpoint } from './endpoint.js';
export { escapeHTML, HTMLBytes, HTMLString, isHTMLString, markHTMLString, unescapeHTML, } from './escape.js';
export { renderJSX } from './jsx.js';
export { addAttribute, createHeadAndContent, defineScriptVars, Fragment, maybeRenderHead, renderTemplate as render, renderComponent, Renderer as Renderer, renderHead, renderHTMLElement, renderPage, renderScript, renderScriptElement, renderSlot, renderSlotToString, renderTemplate, renderToString, renderUniqueStylesheet, voidElementNames, } from './render/index.js';
export type { AstroComponentFactory, AstroComponentInstance, ComponentSlots, RenderInstruction, } from './render/index.js';
export { createTransitionScope, renderTransition } from './transition.js';
export declare function mergeSlots(...slotted: unknown[]): Record<string, () => any>;
export declare function spreadAttributes(values?: Record<any, any>, _name?: string, { class: scopedClassName }?: {
    class?: string;
}): any;
export declare function defineStyleVars(defs: Record<any, any> | Record<any, any>[]): any;
