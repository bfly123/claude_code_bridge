import type { PaginateFunction, RouteData } from '../../@types/astro.js';
export declare function generatePaginateFunction(routeMatch: RouteData): (...args: Parameters<PaginateFunction>) => ReturnType<PaginateFunction>;
