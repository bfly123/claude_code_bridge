import type { SSRResult } from '../../../../@types/astro.js';
import type { ComponentSlots } from '../slot.js';
import type { AstroComponentFactory } from './factory.js';
import type { RenderDestination } from '../common.js';
type ComponentProps = Record<string | number, any>;
declare const astroComponentInstanceSym: unique symbol;
export declare class AstroComponentInstance {
    [astroComponentInstanceSym]: boolean;
    private readonly result;
    private readonly props;
    private readonly slotValues;
    private readonly factory;
    private returnValue;
    constructor(result: SSRResult, props: ComponentProps, slots: ComponentSlots, factory: AstroComponentFactory);
    init(result: SSRResult): Promise<import("./factory.js").AstroFactoryReturnValue>;
    render(destination: RenderDestination): Promise<void>;
}
export declare function createAstroComponentInstance(result: SSRResult, displayName: string, factory: AstroComponentFactory, props: ComponentProps, slots?: any): AstroComponentInstance;
export declare function isAstroComponentInstance(obj: unknown): obj is AstroComponentInstance;
export {};
