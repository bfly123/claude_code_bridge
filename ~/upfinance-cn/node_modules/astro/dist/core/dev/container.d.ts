import type * as http from 'node:http';
import type { AddressInfo } from 'node:net';
import type { AstroInlineConfig, AstroSettings } from '../../@types/astro.js';
import nodeFs from 'node:fs';
import * as vite from 'vite';
import type { Logger } from '../logger/core.js';
export interface Container {
    fs: typeof nodeFs;
    logger: Logger;
    settings: AstroSettings;
    viteServer: vite.ViteDevServer;
    inlineConfig: AstroInlineConfig;
    restartInFlight: boolean;
    handle: (req: http.IncomingMessage, res: http.ServerResponse) => void;
    close: () => Promise<void>;
}
export interface CreateContainerParams {
    logger: Logger;
    settings: AstroSettings;
    inlineConfig?: AstroInlineConfig;
    isRestart?: boolean;
    fs?: typeof nodeFs;
}
export declare function createContainer({ isRestart, logger, inlineConfig, settings, fs, }: CreateContainerParams): Promise<Container>;
export declare function startContainer({ settings, viteServer, logger, }: Container): Promise<AddressInfo>;
