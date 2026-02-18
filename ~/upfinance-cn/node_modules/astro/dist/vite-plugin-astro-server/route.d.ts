import type http from 'node:http';
import type { ComponentInstance, ManifestData, RouteData } from '../@types/astro.js';
import type { DevPipeline } from './pipeline.js';
type AsyncReturnType<T extends (...args: any) => Promise<any>> = T extends (...args: any) => Promise<infer R> ? R : any;
export interface MatchedRoute {
    route: RouteData;
    filePath: URL;
    resolvedPathname: string;
    preloadedComponent: ComponentInstance;
    mod: ComponentInstance;
}
export declare function matchRoute(pathname: string, manifestData: ManifestData, pipeline: DevPipeline): Promise<MatchedRoute | undefined>;
type HandleRoute = {
    matchedRoute: AsyncReturnType<typeof matchRoute>;
    url: URL;
    pathname: string;
    body: ArrayBuffer | undefined;
    manifestData: ManifestData;
    incomingRequest: http.IncomingMessage;
    incomingResponse: http.ServerResponse;
    pipeline: DevPipeline;
};
export declare function handleRoute({ matchedRoute, url, pathname, body, pipeline, manifestData, incomingRequest, incomingResponse, }: HandleRoute): Promise<void>;
export {};
