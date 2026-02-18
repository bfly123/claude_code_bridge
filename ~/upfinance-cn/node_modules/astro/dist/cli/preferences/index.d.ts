import { type Flags } from '../flags.js';
interface PreferencesOptions {
    flags: Flags;
}
declare const PREFERENCES_SUBCOMMANDS: readonly ["get", "set", "enable", "disable", "delete", "reset", "list"];
export type Subcommand = (typeof PREFERENCES_SUBCOMMANDS)[number];
export declare function preferences(subcommand: string, key: string, value: string | undefined, { flags }: PreferencesOptions): Promise<number>;
export {};
