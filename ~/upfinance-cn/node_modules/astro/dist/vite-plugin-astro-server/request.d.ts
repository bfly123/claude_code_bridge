import type http from 'node:http';
import type { ManifestData } from '../@types/astro.js';
import type { DevServerController } from './controller.js';
import type { DevPipeline } from './pipeline.js';
type HandleRequest = {
    pipeline: DevPipeline;
    manifestData: ManifestData;
    controller: DevServerController;
    incomingRequest: http.IncomingMessage;
    incomingResponse: http.ServerResponse;
};
/** The main logic to route dev server requests to pages in Astro. */
export declare function handleRequest({ pipeline, manifestData, controller, incomingRequest, incomingResponse, }: HandleRequest): Promise<void>;
export {};
