import type { Logger } from '../core/logger/core.js';
type GetPackageOptions = {
    skipAsk?: boolean;
    optional?: boolean;
    cwd?: string;
};
export declare function getPackage<T>(packageName: string, logger: Logger, options: GetPackageOptions, otherDeps?: string[]): Promise<T | undefined>;
/**
 * Get the command to execute and download a package (e.g. `npx`, `yarn dlx`, `pnpm dlx`, etc.)
 * @param packageManager - Optional package manager to use. If not provided, Astro will attempt to detect the preferred package manager.
 * @returns The command to execute and download a package
 */
export declare function getExecCommand(packageManager?: string): Promise<string>;
export declare function fetchPackageJson(scope: string | undefined, name: string, tag: string): Promise<Record<string, any> | Error>;
export declare function fetchPackageVersions(packageName: string): Promise<string[] | Error>;
export {};
