import type { AstroUserConfig } from '../@types/astro.js';
interface EventPayload {
    cliCommand: string;
    config?: ConfigInfo;
    configKeys?: string[];
    flags?: string[];
    optionalIntegrations?: number;
}
type ConfigInfoValue = string | boolean | string[] | undefined;
type ConfigInfoRecord = Record<string, ConfigInfoValue>;
type ConfigInfoBase = {
    [alias in keyof AstroUserConfig]: ConfigInfoValue | ConfigInfoRecord;
};
export interface ConfigInfo extends ConfigInfoBase {
    build: ConfigInfoRecord;
    image: ConfigInfoRecord;
    markdown: ConfigInfoRecord;
    experimental: ConfigInfoRecord;
    legacy: ConfigInfoRecord;
    vite: ConfigInfoRecord | undefined;
}
export declare function eventCliSession(cliCommand: string, userConfig: AstroUserConfig, flags?: Record<string, any>): {
    eventName: string;
    payload: EventPayload;
}[];
export {};
