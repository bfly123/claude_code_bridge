import type { AstroRenderer, SSRLoadedRenderer } from '../../@types/astro.js';
import type { ModuleLoader } from '../module-loader/index.js';
export declare function loadRenderer(renderer: AstroRenderer, moduleLoader: ModuleLoader): Promise<SSRLoadedRenderer | undefined>;
