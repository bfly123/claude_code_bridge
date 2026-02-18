import type { RouteData, SSRResult } from '../../../../@types/astro.js';
import type { AstroComponentFactory } from './factory.js';
export declare function renderToString(result: SSRResult, componentFactory: AstroComponentFactory, props: any, children: any, isPage?: boolean, route?: RouteData): Promise<string | Response>;
export declare function renderToReadableStream(result: SSRResult, componentFactory: AstroComponentFactory, props: any, children: any, isPage?: boolean, route?: RouteData): Promise<ReadableStream | Response>;
export declare function renderToAsyncIterable(result: SSRResult, componentFactory: AstroComponentFactory, props: any, children: any, isPage?: boolean, route?: RouteData): Promise<AsyncIterable<Uint8Array> | Response>;
