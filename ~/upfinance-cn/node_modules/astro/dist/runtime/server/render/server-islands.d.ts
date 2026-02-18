import type { SSRResult } from '../../../@types/astro.js';
import type { RenderInstance } from './common.js';
import { type ComponentSlots } from './slot.js';
export declare function containsServerDirective(props: Record<string | number, any>): boolean;
export declare function renderServerIsland(result: SSRResult, _displayName: string, props: Record<string | number, any>, slots: ComponentSlots): RenderInstance;
