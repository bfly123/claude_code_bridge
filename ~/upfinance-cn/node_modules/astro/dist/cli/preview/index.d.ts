import { type Flags } from '../flags.js';
interface PreviewOptions {
    flags: Flags;
}
export declare function preview({ flags }: PreviewOptions): Promise<import("../../@types/astro.js").PreviewServer | undefined>;
export {};
