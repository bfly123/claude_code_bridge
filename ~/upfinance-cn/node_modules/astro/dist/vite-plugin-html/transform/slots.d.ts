import type { Root } from 'hast';
import type { Plugin } from 'unified';
import type MagicString from 'magic-string';
declare const rehypeSlots: Plugin<[{
    s: MagicString;
}], Root>;
export default rehypeSlots;
export declare const SLOT_PREFIX = "___SLOTS___";
