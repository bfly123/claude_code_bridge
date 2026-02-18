export declare function pathify(path: string): string;
export declare function instantiateEmscriptenWasm<T extends EmscriptenWasm.Module>(factory: EmscriptenWasm.ModuleFactory<T>, bytes: Uint8Array): Promise<T>;
export declare function dirname(url: string): string;
/**
 * On certain serverless hosts, our ESM bundle is transpiled to CJS before being run, which means
 * import.meta.url is undefined, so we'll fall back to __filename in those cases
 * We should be able to remove this once https://github.com/netlify/zip-it-and-ship-it/issues/750 is fixed
 */
export declare function getModuleURL(url: string | undefined): string;
