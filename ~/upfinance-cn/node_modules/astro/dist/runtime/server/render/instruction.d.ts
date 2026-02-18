import type { HydrationMetadata } from '../hydration.js';
export type RenderDirectiveInstruction = {
    type: 'directive';
    hydration: HydrationMetadata;
};
export type RenderHeadInstruction = {
    type: 'head';
};
/**
 * Render a renderer-specific hydration script before the first component of that
 * framework
 */
export type RendererHydrationScriptInstruction = {
    type: 'renderer-hydration-script';
    rendererName: string;
    render: () => string;
};
export type MaybeRenderHeadInstruction = {
    type: 'maybe-head';
};
export type RenderInstruction = RenderDirectiveInstruction | RenderHeadInstruction | MaybeRenderHeadInstruction | RendererHydrationScriptInstruction;
export declare function createRenderInstruction(instruction: RenderDirectiveInstruction): RenderDirectiveInstruction;
export declare function createRenderInstruction(instruction: RendererHydrationScriptInstruction): RendererHydrationScriptInstruction;
export declare function createRenderInstruction(instruction: RenderHeadInstruction): RenderHeadInstruction;
export declare function createRenderInstruction(instruction: MaybeRenderHeadInstruction): MaybeRenderHeadInstruction;
export declare function isRenderInstruction(chunk: any): chunk is RenderInstruction;
