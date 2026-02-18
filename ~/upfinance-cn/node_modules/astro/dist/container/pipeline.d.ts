import type { ComponentInstance, RewritePayload, RouteData, SSRResult } from '../@types/astro.js';
import { type HeadElements, Pipeline, type TryRewriteResult } from '../core/base-pipeline.js';
export declare class ContainerPipeline extends Pipeline {
    #private;
    static create({ logger, manifest, renderers, resolve, serverLike, streaming, }: Pick<ContainerPipeline, 'logger' | 'manifest' | 'renderers' | 'resolve' | 'serverLike' | 'streaming'>): ContainerPipeline;
    componentMetadata(_routeData: RouteData): Promise<SSRResult['componentMetadata']> | void;
    headElements(routeData: RouteData): Promise<HeadElements> | HeadElements;
    tryRewrite(payload: RewritePayload, request: Request): Promise<TryRewriteResult>;
    insertRoute(route: RouteData, componentInstance: ComponentInstance): void;
    getComponentByRoute(_routeData: RouteData): Promise<ComponentInstance>;
}
