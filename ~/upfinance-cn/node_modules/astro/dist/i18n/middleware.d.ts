import type { MiddlewareHandler, SSRManifest } from '../@types/astro.js';
export declare function createI18nMiddleware(i18n: SSRManifest['i18n'], base: SSRManifest['base'], trailingSlash: SSRManifest['trailingSlash'], format: SSRManifest['buildFormat']): MiddlewareHandler;
