export type ErrorState = 'fresh' | 'error';
export interface RouteState {
    state: ErrorState;
    error?: Error;
}
export interface ServerState {
    routes: Map<string, RouteState>;
    state: ErrorState;
    error?: Error;
}
export declare function createServerState(): ServerState;
export declare function hasAnyFailureState(serverState: ServerState): boolean;
export declare function setRouteError(serverState: ServerState, pathname: string, error: Error): void;
export declare function setServerError(serverState: ServerState, error: Error): void;
export declare function clearRouteError(serverState: ServerState, pathname: string): void;
