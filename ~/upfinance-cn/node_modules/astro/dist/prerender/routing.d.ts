import type { AstroSettings, ComponentInstance, RouteData } from '../@types/astro.js';
import type { DevPipeline } from '../vite-plugin-astro-server/pipeline.js';
type GetSortedPreloadedMatchesParams = {
    pipeline: DevPipeline;
    matches: RouteData[];
    settings: AstroSettings;
};
export declare function getSortedPreloadedMatches({ pipeline, matches, settings, }: GetSortedPreloadedMatchesParams): Promise<PreloadAndSetPrerenderStatusResult[]>;
type PreloadAndSetPrerenderStatusResult = {
    filePath: URL;
    route: RouteData;
    preloadedComponent: ComponentInstance;
};
export {};
