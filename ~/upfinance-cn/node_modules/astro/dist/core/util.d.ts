import type { AstroConfig, AstroSettings, RouteType } from '../@types/astro.js';
/** Returns true if argument is an object of any prototype/class (but not null). */
export declare function isObject(value: unknown): value is Record<string, any>;
/** Cross-realm compatible URL */
export declare function isURL(value: unknown): value is URL;
/** Check if a file is a markdown file based on its extension */
export declare function isMarkdownFile(fileId: string, option?: {
    suffix?: string;
}): boolean;
/** Wraps an object in an array. If an array is passed, ignore it. */
export declare function arraify<T>(target: T | T[]): T[];
export declare function padMultilineString(source: string, n?: number): string;
/**
 * Get the correct output filename for a route, based on your config.
 * Handles both "/foo" and "foo" `name` formats.
 * Handles `/404` and `/` correctly.
 */
export declare function getOutputFilename(astroConfig: AstroConfig, name: string, type: RouteType): string;
/** is a specifier an npm package? */
export declare function parseNpmName(spec: string): {
    scope?: string;
    name: string;
    subpath?: string;
} | undefined;
/**
 * Convert file URL to ID for viteServer.moduleGraph.idToModuleMap.get(:viteID)
 * Format:
 *   Linux/Mac:  /Users/astro/code/my-project/src/pages/index.astro
 *   Windows:    C:/Users/astro/code/my-project/src/pages/index.astro
 */
export declare function viteID(filePath: URL): string;
export declare const VALID_ID_PREFIX = "/@id/";
export declare const NULL_BYTE_PLACEHOLDER = "__x00__";
export declare function unwrapId(id: string): string;
export declare function resolvePages(config: AstroConfig): URL;
export declare function isPage(file: URL, settings: AstroSettings): boolean;
export declare function isEndpoint(file: URL, settings: AstroSettings): boolean;
export declare function isServerLikeOutput(config: AstroConfig): boolean;
export declare function isModeServerWithNoAdapter(settings: AstroSettings): boolean;
export declare function isContentCollectionsCacheEnabled(config: AstroConfig): boolean;
export declare function resolveJsToTs(filePath: string): string;
/**
 * Set a default NODE_ENV so Vite doesn't set an incorrect default when loading the Astro config
 */
export declare function ensureProcessNodeEnv(defaultNodeEnv: string): void;
