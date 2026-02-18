import type { AstroIntegration, AstroSettings } from '../@types/astro.js';
/**
 * This integration is applied when the user is using Actions in their project.
 * It will inject the necessary routes and middlewares to handle actions.
 */
export default function astroIntegrationActionsRouteHandler({ settings, }: {
    settings: AstroSettings;
}): AstroIntegration;
