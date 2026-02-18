import type { ZodType } from 'zod';
import type { ActionAccept, ActionClient } from './server.js';
/**
 * Get server-side action based on the route path.
 * Imports from the virtual module `astro:internal-actions`, which maps to
 * the user's `src/actions/index.ts` file at build-time.
 */
export declare function getAction(path: string): Promise<ActionClient<unknown, ActionAccept, ZodType>>;
