import { type SerializedActionResult } from './virtual/shared.js';
export type ActionPayload = {
    actionResult: SerializedActionResult;
    actionName: string;
};
export type Locals = {
    _actionPayload: ActionPayload;
};
export declare const onRequest: import("../../@types/astro.js").MiddlewareHandler;
