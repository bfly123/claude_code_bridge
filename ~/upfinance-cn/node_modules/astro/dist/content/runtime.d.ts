import type { MarkdownHeading } from '@astrojs/markdown-remark';
import { z } from 'zod';
import { type AstroComponentFactory } from '../runtime/server/index.js';
import { type DataEntry } from './data-store.js';
import type { ContentLookupMap } from './utils.js';
type LazyImport = () => Promise<any>;
type GlobResult = Record<string, LazyImport>;
type CollectionToEntryMap = Record<string, GlobResult>;
type GetEntryImport = (collection: string, lookupId: string) => Promise<LazyImport>;
export declare function defineCollection(config: any): any;
export declare function createCollectionToGlobResultMap({ globResult, contentDir, }: {
    globResult: GlobResult;
    contentDir: string;
}): CollectionToEntryMap;
export declare function createGetCollection({ contentCollectionToEntryMap, dataCollectionToEntryMap, getRenderEntryImport, cacheEntriesByCollection, }: {
    contentCollectionToEntryMap: CollectionToEntryMap;
    dataCollectionToEntryMap: CollectionToEntryMap;
    getRenderEntryImport: GetEntryImport;
    cacheEntriesByCollection: Map<string, any[]>;
}): (collection: string, filter?: (entry: any) => unknown) => Promise<any[]>;
export declare function createGetEntryBySlug({ getEntryImport, getRenderEntryImport, collectionNames, }: {
    getEntryImport: GetEntryImport;
    getRenderEntryImport: GetEntryImport;
    collectionNames: Set<string>;
}): (collection: string, slug: string) => Promise<{
    id: any;
    slug: any;
    body: any;
    collection: any;
    data: any;
    render(): Promise<RenderResult>;
} | undefined>;
export declare function createGetDataEntryById({ getEntryImport, collectionNames, }: {
    getEntryImport: GetEntryImport;
    collectionNames: Set<string>;
}): (collection: string, id: string) => Promise<{
    id: any;
    collection: any;
    data: any;
} | undefined>;
type ContentEntryResult = {
    id: string;
    slug: string;
    body: string;
    collection: string;
    data: Record<string, any>;
    render(): Promise<RenderResult>;
};
type DataEntryResult = {
    id: string;
    collection: string;
    data: Record<string, any>;
};
type EntryLookupObject = {
    collection: string;
    id: string;
} | {
    collection: string;
    slug: string;
};
export declare function createGetEntry({ getEntryImport, getRenderEntryImport, collectionNames, }: {
    getEntryImport: GetEntryImport;
    getRenderEntryImport: GetEntryImport;
    collectionNames: Set<string>;
}): (collectionOrLookupObject: string | EntryLookupObject, _lookupId?: string) => Promise<ContentEntryResult | DataEntryResult | undefined>;
export declare function createGetEntries(getEntry: ReturnType<typeof createGetEntry>): (entries: {
    collection: string;
    id: string;
}[] | {
    collection: string;
    slug: string;
}[]) => Promise<(ContentEntryResult | DataEntryResult | undefined)[]>;
type RenderResult = {
    Content: AstroComponentFactory;
    headings: MarkdownHeading[];
    remarkPluginFrontmatter: Record<string, any>;
};
export declare function renderEntry(entry: DataEntry | {
    render: () => Promise<{
        Content: AstroComponentFactory;
    }>;
}): Promise<{
    Content: AstroComponentFactory;
}>;
export declare function createReference({ lookupMap }: {
    lookupMap: ContentLookupMap;
}): (collection: string) => z.ZodEffects<z.ZodUnion<[z.ZodString, z.ZodObject<{
    id: z.ZodString;
    collection: z.ZodString;
}, "strip", z.ZodTypeAny, {
    id: string;
    collection: string;
}, {
    id: string;
    collection: string;
}>, z.ZodObject<{
    slug: z.ZodString;
    collection: z.ZodString;
}, "strip", z.ZodTypeAny, {
    collection: string;
    slug: string;
}, {
    collection: string;
    slug: string;
}>]>, {
    id: string;
    collection: string;
} | {
    slug: string;
    collection: string;
} | undefined, string | {
    id: string;
    collection: string;
} | {
    collection: string;
    slug: string;
}>;
export {};
