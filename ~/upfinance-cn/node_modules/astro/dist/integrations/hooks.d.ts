import fsMod from 'node:fs';
import type { AddressInfo } from 'node:net';
import type { InlineConfig, ViteDevServer } from 'vite';
import type { AstroAdapter, AstroConfig, AstroSettings, RouteData, RouteOptions } from '../@types/astro.js';
import type { SerializedSSRManifest } from '../core/app/types.js';
import type { PageBuildData } from '../core/build/types.js';
import type { Logger } from '../core/logger/core.js';
export declare function getToolbarServerCommunicationHelpers(server: ViteDevServer): {
    /**
     * Send a message to the dev toolbar that an app can listen for. The payload can be any serializable data.
     * @param event - The event name
     * @param payload - The payload to send
     */
    send: <T>(event: string, payload: T) => void;
    /**
     * Receive a message from a dev toolbar app.
     * @param event
     * @param callback
     */
    on: <T>(event: string, callback: (data: T) => void) => void;
    /**
     * Fired when an app is initialized.
     * @param appId - The id of the app that was initialized
     * @param callback - The callback to run when the app is initialized
     */
    onAppInitialized: (appId: string, callback: (data: Record<string, never>) => void) => void;
    /**
     * Fired when an app is toggled on or off.
     * @param appId - The id of the app that was toggled
     * @param callback - The callback to run when the app is toggled
     */
    onAppToggled: (appId: string, callback: (data: {
        state: boolean;
    }) => void) => void;
};
export declare function normalizeInjectedTypeFilename(filename: string, integrationName: string): string;
export declare function runHookConfigSetup({ settings, command, logger, isRestart, fs, }: {
    settings: AstroSettings;
    command: 'dev' | 'build' | 'preview' | 'sync';
    logger: Logger;
    isRestart?: boolean;
    fs?: typeof fsMod;
}): Promise<AstroSettings>;
export declare function runHookConfigDone({ settings, logger, }: {
    settings: AstroSettings;
    logger: Logger;
}): Promise<void>;
export declare function runHookServerSetup({ config, server, logger, }: {
    config: AstroConfig;
    server: ViteDevServer;
    logger: Logger;
}): Promise<void>;
export declare function runHookServerStart({ config, address, logger, }: {
    config: AstroConfig;
    address: AddressInfo;
    logger: Logger;
}): Promise<void>;
export declare function runHookServerDone({ config, logger, }: {
    config: AstroConfig;
    logger: Logger;
}): Promise<void>;
export declare function runHookBuildStart({ config, logging, }: {
    config: AstroConfig;
    logging: Logger;
}): Promise<void>;
export declare function runHookBuildSetup({ config, vite, pages, target, logger, }: {
    config: AstroConfig;
    vite: InlineConfig;
    pages: Map<string, PageBuildData>;
    target: 'server' | 'client';
    logger: Logger;
}): Promise<InlineConfig>;
type RunHookBuildSsr = {
    config: AstroConfig;
    manifest: SerializedSSRManifest;
    logger: Logger;
    entryPoints: Map<RouteData, URL>;
    middlewareEntryPoint: URL | undefined;
};
export declare function runHookBuildSsr({ config, manifest, logger, entryPoints, middlewareEntryPoint, }: RunHookBuildSsr): Promise<void>;
export declare function runHookBuildGenerated({ config, logger, }: {
    config: AstroConfig;
    logger: Logger;
}): Promise<void>;
type RunHookBuildDone = {
    config: AstroConfig;
    pages: string[];
    routes: RouteData[];
    logging: Logger;
    cacheManifest: boolean;
};
export declare function runHookBuildDone({ config, pages, routes, logging, cacheManifest, }: RunHookBuildDone): Promise<void>;
export declare function runHookRouteSetup({ route, settings, logger, }: {
    route: RouteOptions;
    settings: AstroSettings;
    logger: Logger;
}): Promise<void>;
export declare function isFunctionPerRouteEnabled(adapter: AstroAdapter | undefined): boolean;
export {};
