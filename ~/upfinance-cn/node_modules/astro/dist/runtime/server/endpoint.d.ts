import type { APIContext, EndpointHandler } from '../../@types/astro.js';
import type { Logger } from '../../core/logger/core.js';
/** Renders an endpoint request to completion, returning the body. */
export declare function renderEndpoint(mod: EndpointHandler, context: APIContext, ssr: boolean, logger: Logger): Promise<Response>;
