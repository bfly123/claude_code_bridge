import type { PropagationHint } from '../../@types/astro.js';
import type { AstroComponentFactory } from './render/index.js';
interface CreateComponentOptions {
    factory: AstroComponentFactory;
    moduleId?: string;
    propagation?: PropagationHint;
}
export declare function createComponent(arg1: AstroComponentFactory | CreateComponentOptions, moduleId?: string, propagation?: PropagationHint): AstroComponentFactory;
export {};
