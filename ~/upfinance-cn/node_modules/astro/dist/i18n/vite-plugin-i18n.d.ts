import type * as vite from 'vite';
import type { AstroConfig, AstroSettings } from '../@types/astro.js';
type AstroInternationalization = {
    settings: AstroSettings;
};
export interface I18nInternalConfig extends Pick<AstroConfig, 'base' | 'site' | 'trailingSlash'>, Pick<AstroConfig['build'], 'format'> {
    i18n: AstroConfig['i18n'];
    isBuild: boolean;
}
export default function astroInternationalization({ settings, }: AstroInternationalization): vite.Plugin;
export {};
