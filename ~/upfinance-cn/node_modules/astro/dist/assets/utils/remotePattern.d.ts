import type { AstroConfig } from '../../@types/astro.js';
export type RemotePattern = {
    hostname?: string;
    pathname?: string;
    protocol?: string;
    port?: string;
};
export declare function matchPattern(url: URL, remotePattern: RemotePattern): boolean;
export declare function matchPort(url: URL, port?: string): boolean;
export declare function matchProtocol(url: URL, protocol?: string): boolean;
export declare function matchHostname(url: URL, hostname?: string, allowWildcard?: boolean): boolean;
export declare function matchPathname(url: URL, pathname?: string, allowWildcard?: boolean): boolean;
export declare function isRemoteAllowed(src: string, { domains, remotePatterns, }: Partial<Pick<AstroConfig['image'], 'domains' | 'remotePatterns'>>): boolean;
