import type { AstroAdapterFeatures, AstroConfig, AstroFeatureMap } from '../@types/astro.js';
import type { Logger } from '../core/logger/core.js';
type ValidationResult = {
    [Property in keyof AstroFeatureMap]: boolean;
};
/**
 * Checks whether an adapter supports certain features that are enabled via Astro configuration.
 *
 * If a configuration is enabled and "unlocks" a feature, but the adapter doesn't support, the function
 * will throw a runtime error.
 *
 */
export declare function validateSupportedFeatures(adapterName: string, featureMap: AstroFeatureMap, config: AstroConfig, adapterFeatures: AstroAdapterFeatures | undefined, logger: Logger): ValidationResult;
export {};
