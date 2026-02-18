import type { AstroSettings, ManifestData, RoutePart } from '../../../@types/astro.js';
import type { Logger } from '../../logger/core.js';
import nodeFs from 'node:fs';
export declare function getParts(part: string, file: string): RoutePart[];
export declare function validateSegment(segment: string, file?: string): void;
export interface CreateRouteManifestParams {
    /** Astro Settings object */
    settings: AstroSettings;
    /** Current working directory */
    cwd?: string;
    /** fs module, for testing */
    fsMod?: typeof nodeFs;
}
/** Create manifest of all static routes */
export declare function createRouteManifest(params: CreateRouteManifestParams, logger: Logger): ManifestData;
