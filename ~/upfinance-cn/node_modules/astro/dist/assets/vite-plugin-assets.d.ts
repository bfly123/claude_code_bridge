import type * as vite from 'vite';
import type { AstroPluginOptions } from '../@types/astro.js';
export default function assets({ settings, mode, }: AstroPluginOptions & {
    mode: string;
}): vite.Plugin[];
