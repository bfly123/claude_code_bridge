import type fsMod from 'node:fs';
import type { APIContext } from '../@types/astro.js';
import type { Locals } from './runtime/middleware.js';
import { type ActionAPIContext } from './runtime/utils.js';
export declare function hasActionPayload(locals: APIContext['locals']): locals is Locals;
export declare function createGetActionResult(locals: APIContext['locals']): APIContext['getActionResult'];
export declare function createCallAction(context: ActionAPIContext): APIContext['callAction'];
/**
 * Check whether the Actions config file is present.
 */
export declare function isActionsFilePresent(fs: typeof fsMod, srcDir: URL): Promise<boolean>;
