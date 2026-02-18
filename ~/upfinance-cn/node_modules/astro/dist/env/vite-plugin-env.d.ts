import type fsMod from 'node:fs';
import { type Plugin } from 'vite';
import type { AstroSettings } from '../@types/astro.js';
interface AstroEnvVirtualModPluginParams {
    settings: AstroSettings;
    mode: 'dev' | 'build' | string;
    fs: typeof fsMod;
    sync: boolean;
}
export declare function astroEnv({ settings, mode, fs, sync, }: AstroEnvVirtualModPluginParams): Plugin | undefined;
export {};
