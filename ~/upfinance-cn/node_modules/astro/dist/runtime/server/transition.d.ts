import type { SSRResult, TransitionAnimationPair, TransitionAnimationValue } from '../../@types/astro.js';
export declare function createTransitionScope(result: SSRResult, hash: string): string;
export declare function renderTransition(result: SSRResult, hash: string, animationName: TransitionAnimationValue | undefined, transitionName: string): string;
export declare function createAnimationScope(transitionName: string, animations: Record<string, TransitionAnimationPair>): {
    scope: string;
    styles: string;
};
