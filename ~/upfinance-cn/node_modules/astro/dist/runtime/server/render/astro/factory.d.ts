import type { PropagationHint, SSRResult } from '../../../../@types/astro.js';
import type { HeadAndContent } from './head-and-content.js';
import type { RenderTemplateResult } from './render-template.js';
export type AstroFactoryReturnValue = RenderTemplateResult | Response | HeadAndContent;
export interface AstroComponentFactory {
    (result: any, props: any, slots: any): AstroFactoryReturnValue | Promise<AstroFactoryReturnValue>;
    isAstroComponentFactory?: boolean;
    moduleId?: string | undefined;
    propagation?: PropagationHint;
}
export declare function isAstroComponentFactory(obj: any): obj is AstroComponentFactory;
export declare function isAPropagatingComponent(result: SSRResult, factory: AstroComponentFactory): boolean;
