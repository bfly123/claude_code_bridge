import type { PluginContext } from 'rollup';
import { z } from 'zod';
export declare function createImage(pluginContext: PluginContext, shouldEmitFile: boolean, entryFilePath: string): () => z.ZodEffects<z.ZodString, z.ZodNever | {
    ASTRO_ASSET: string;
    width: number;
    height: number;
    format: import("../assets/types.js").ImageInputFormat;
    src: string;
    fsPath: string;
    orientation?: number | undefined;
}, string>;
