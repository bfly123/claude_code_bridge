import { type ProxifiedModule } from 'magicast';
import { type Flags } from '../flags.js';
interface AddOptions {
    flags: Flags;
}
interface IntegrationInfo {
    id: string;
    packageName: string;
    dependencies: [name: string, version: string][];
    type: 'integration' | 'adapter';
}
export declare function add(names: string[], { flags }: AddOptions): Promise<void>;
export declare function setAdapter(mod: ProxifiedModule<any>, adapter: IntegrationInfo, exportName: string): void;
export {};
