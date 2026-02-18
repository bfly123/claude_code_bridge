import type { RenderTemplateResult } from './render-template.js';
declare const headAndContentSym: unique symbol;
export type HeadAndContent = {
    [headAndContentSym]: true;
    head: string;
    content: RenderTemplateResult;
};
export declare function isHeadAndContent(obj: unknown): obj is HeadAndContent;
export declare function createHeadAndContent(head: string, content: RenderTemplateResult): HeadAndContent;
export {};
