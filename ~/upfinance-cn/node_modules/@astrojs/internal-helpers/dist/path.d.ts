/**
 * A set of common path utilities commonly used through the Astro core and integration
 * projects. These do things like ensure a forward slash prepends paths.
 */
export declare function appendExtension(path: string, extension: string): string;
export declare function appendForwardSlash(path: string): string;
export declare function prependForwardSlash(path: string): string;
export declare function collapseDuplicateSlashes(path: string): string;
export declare function removeTrailingForwardSlash(path: string): string;
export declare function removeLeadingForwardSlash(path: string): string;
export declare function removeLeadingForwardSlashWindows(path: string): string;
export declare function trimSlashes(path: string): string;
export declare function startsWithForwardSlash(path: string): boolean;
export declare function startsWithDotDotSlash(path: string): boolean;
export declare function startsWithDotSlash(path: string): boolean;
export declare function isRelativePath(path: string): boolean;
export declare function joinPaths(...paths: (string | undefined)[]): string;
export declare function removeFileExtension(path: string): string;
export declare function removeQueryString(path: string): string;
export declare function isRemotePath(src: string): boolean;
export declare function slash(path: string): string;
export declare function fileExtension(path: string): string;
export declare function removeBase(path: string, base: string): string;
