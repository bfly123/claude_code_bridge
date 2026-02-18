import { type PathLike } from 'node:fs';
import { type DataEntry, DataStore, type RenderedContent } from './data-store.js';
/**
 * Extends the DataStore with the ability to change entries and write them to disk.
 * This is kept as a separate class to avoid needing node builtins at runtime, when read-only access is all that is needed.
 */
export declare class MutableDataStore extends DataStore {
    #private;
    set(collectionName: string, key: string, value: unknown): void;
    delete(collectionName: string, key: string): void;
    clear(collectionName: string): void;
    clearAll(): void;
    addAssetImport(assetImport: string, filePath?: string): void;
    addAssetImports(assets: Array<string>, filePath?: string): void;
    addModuleImport(fileName: string): void;
    writeAssetImports(filePath: PathLike): Promise<void>;
    writeModuleImports(filePath: PathLike): Promise<void>;
    scopedStore(collectionName: string): ScopedDataStore;
    /**
     * Returns a MetaStore for a given collection, or if no collection is provided, the default meta collection.
     */
    metaStore(collectionName?: string): MetaStore;
    toString(): string;
    writeToDisk(filePath: PathLike): Promise<void>;
    /**
     * Attempts to load a MutableDataStore from the virtual module.
     * This only works in Vite.
     */
    static fromModule(): Promise<MutableDataStore>;
    static fromMap(data: Map<string, Map<string, any>>): Promise<MutableDataStore>;
    static fromString(data: string): Promise<MutableDataStore>;
    static fromFile(filePath: string | URL): Promise<MutableDataStore>;
}
export interface ScopedDataStore {
    get: <TData extends Record<string, unknown> = Record<string, unknown>>(key: string) => DataEntry<TData> | undefined;
    entries: () => Array<[id: string, DataEntry]>;
    set: <TData extends Record<string, unknown>>(opts: {
        /** The ID of the entry. Must be unique per collection. */
        id: string;
        /** The data to store. */
        data: TData;
        /** The raw body of the content, if applicable. */
        body?: string;
        /** The file path of the content, if applicable. Relative to the site root. */
        filePath?: string;
        /** A content digest, to check if the content has changed. */
        digest?: number | string;
        /** The rendered content, if applicable. */
        rendered?: RenderedContent;
        /**
         * If an entry is a deferred, its rendering phase is delegated to a virtual module during the runtime phase.
         */
        deferredRender?: boolean;
    }) => boolean;
    values: () => Array<DataEntry>;
    keys: () => Array<string>;
    delete: (key: string) => void;
    clear: () => void;
    has: (key: string) => boolean;
    /**
     * Adds a single asset to the store. This asset will be transformed
     * by Vite, and the URL will be available in the final build.
     * @param fileName
     * @param specifier
     * @returns
     */
    addModuleImport: (fileName: string) => void;
}
/**
 * A key-value store for metadata strings. Useful for storing things like sync tokens.
 */
export interface MetaStore {
    get: (key: string) => string | undefined;
    set: (key: string, value: string) => void;
    has: (key: string) => boolean;
    delete: (key: string) => void;
}
