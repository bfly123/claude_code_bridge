import { promises as fs, existsSync } from "node:fs";
import * as devalue from "devalue";
import { Traverse } from "neotraverse/modern";
import { imageSrcToImportId, importIdToSymbolName } from "../assets/utils/resolveImports.js";
import { AstroError, AstroErrorData } from "../core/errors/index.js";
import { IMAGE_IMPORT_PREFIX } from "./consts.js";
import { DataStore } from "./data-store.js";
import { contentModuleToId } from "./utils.js";
const SAVE_DEBOUNCE_MS = 500;
class MutableDataStore extends DataStore {
  #file;
  #assetsFile;
  #modulesFile;
  #saveTimeout;
  #assetsSaveTimeout;
  #modulesSaveTimeout;
  #dirty = false;
  #assetsDirty = false;
  #modulesDirty = false;
  #assetImports = /* @__PURE__ */ new Set();
  #moduleImports = /* @__PURE__ */ new Map();
  set(collectionName, key, value) {
    const collection = this._collections.get(collectionName) ?? /* @__PURE__ */ new Map();
    collection.set(String(key), value);
    this._collections.set(collectionName, collection);
    this.#saveToDiskDebounced();
  }
  delete(collectionName, key) {
    const collection = this._collections.get(collectionName);
    if (collection) {
      collection.delete(String(key));
      this.#saveToDiskDebounced();
    }
  }
  clear(collectionName) {
    this._collections.delete(collectionName);
    this.#saveToDiskDebounced();
  }
  clearAll() {
    this._collections.clear();
    this.#saveToDiskDebounced();
  }
  addAssetImport(assetImport, filePath) {
    const id = imageSrcToImportId(assetImport, filePath);
    if (id) {
      this.#assetImports.add(id);
      this.#writeAssetsImportsDebounced();
    }
  }
  addAssetImports(assets, filePath) {
    assets.forEach((asset) => this.addAssetImport(asset, filePath));
  }
  addModuleImport(fileName) {
    const id = contentModuleToId(fileName);
    if (id) {
      this.#moduleImports.set(fileName, id);
      this.#writeModulesImportsDebounced();
    }
  }
  async writeAssetImports(filePath) {
    this.#assetsFile = filePath;
    if (this.#assetImports.size === 0) {
      try {
        await fs.writeFile(filePath, "export default new Map();");
      } catch (err) {
        throw new AstroError(AstroErrorData.UnknownFilesystemError, { cause: err });
      }
    }
    if (!this.#assetsDirty && existsSync(filePath)) {
      return;
    }
    const imports = [];
    const exports = [];
    this.#assetImports.forEach((id) => {
      const symbol = importIdToSymbolName(id);
      imports.push(`import ${symbol} from '${id}';`);
      exports.push(`[${JSON.stringify(id)}, ${symbol}]`);
    });
    const code = (
      /* js */
      `
${imports.join("\n")}
export default new Map([${exports.join(", ")}]);
		`
    );
    try {
      await fs.writeFile(filePath, code);
    } catch (err) {
      throw new AstroError(AstroErrorData.UnknownFilesystemError, { cause: err });
    }
    this.#assetsDirty = false;
  }
  async writeModuleImports(filePath) {
    this.#modulesFile = filePath;
    if (this.#moduleImports.size === 0) {
      try {
        await fs.writeFile(filePath, "export default new Map();");
      } catch (err) {
        throw new AstroError(AstroErrorData.UnknownFilesystemError, { cause: err });
      }
    }
    if (!this.#modulesDirty && existsSync(filePath)) {
      return;
    }
    const lines = [];
    for (const [fileName, specifier] of this.#moduleImports) {
      lines.push(`['${fileName}', () => import('${specifier}')]`);
    }
    const code = `
export default new Map([
${lines.join(",\n")}]);
		`;
    try {
      await fs.writeFile(filePath, code);
    } catch (err) {
      throw new AstroError(AstroErrorData.UnknownFilesystemError, { cause: err });
    }
    this.#modulesDirty = false;
  }
  #writeAssetsImportsDebounced() {
    this.#assetsDirty = true;
    if (this.#assetsFile) {
      if (this.#assetsSaveTimeout) {
        clearTimeout(this.#assetsSaveTimeout);
      }
      this.#assetsSaveTimeout = setTimeout(() => {
        this.#assetsSaveTimeout = void 0;
        this.writeAssetImports(this.#assetsFile);
      }, SAVE_DEBOUNCE_MS);
    }
  }
  #writeModulesImportsDebounced() {
    this.#modulesDirty = true;
    if (this.#modulesFile) {
      if (this.#modulesSaveTimeout) {
        clearTimeout(this.#modulesSaveTimeout);
      }
      this.#modulesSaveTimeout = setTimeout(() => {
        this.#modulesSaveTimeout = void 0;
        this.writeModuleImports(this.#modulesFile);
      }, SAVE_DEBOUNCE_MS);
    }
  }
  #saveToDiskDebounced() {
    this.#dirty = true;
    if (this.#file) {
      if (this.#saveTimeout) {
        clearTimeout(this.#saveTimeout);
      }
      this.#saveTimeout = setTimeout(() => {
        this.#saveTimeout = void 0;
        this.writeToDisk(this.#file);
      }, SAVE_DEBOUNCE_MS);
    }
  }
  scopedStore(collectionName) {
    return {
      get: (key) => this.get(collectionName, key),
      entries: () => this.entries(collectionName),
      values: () => this.values(collectionName),
      keys: () => this.keys(collectionName),
      set: ({ id: key, data, body, filePath, deferredRender, digest, rendered, assetImports }) => {
        if (!key) {
          throw new Error(`ID must be a non-empty string`);
        }
        const id = String(key);
        if (digest) {
          const existing = this.get(collectionName, id);
          if (existing && existing.digest === digest) {
            return false;
          }
        }
        const foundAssets = new Set(assetImports);
        new Traverse(data).forEach((_, val) => {
          if (typeof val === "string" && val.startsWith(IMAGE_IMPORT_PREFIX)) {
            const src = val.replace(IMAGE_IMPORT_PREFIX, "");
            foundAssets.add(src);
          }
        });
        const entry = {
          id,
          data
        };
        if (body) {
          entry.body = body;
        }
        if (filePath) {
          if (filePath.startsWith("/")) {
            throw new Error(`File path must be relative to the site root. Got: ${filePath}`);
          }
          entry.filePath = filePath;
        }
        if (foundAssets.size) {
          entry.assetImports = Array.from(foundAssets);
          this.addAssetImports(entry.assetImports, filePath);
        }
        if (digest) {
          entry.digest = digest;
        }
        if (rendered) {
          entry.rendered = rendered;
        }
        if (deferredRender) {
          entry.deferredRender = deferredRender;
          if (filePath) {
            this.addModuleImport(filePath);
          }
        }
        this.set(collectionName, id, entry);
        return true;
      },
      delete: (key) => this.delete(collectionName, key),
      clear: () => this.clear(collectionName),
      has: (key) => this.has(collectionName, key),
      addAssetImport: (assetImport, fileName) => this.addAssetImport(assetImport, fileName),
      addAssetImports: (assets, fileName) => this.addAssetImports(assets, fileName),
      addModuleImport: (fileName) => this.addModuleImport(fileName)
    };
  }
  /**
   * Returns a MetaStore for a given collection, or if no collection is provided, the default meta collection.
   */
  metaStore(collectionName = ":meta") {
    const collectionKey = `meta:${collectionName}`;
    return {
      get: (key) => this.get(collectionKey, key),
      set: (key, data) => this.set(collectionKey, key, data),
      delete: (key) => this.delete(collectionKey, key),
      has: (key) => this.has(collectionKey, key)
    };
  }
  toString() {
    return devalue.stringify(this._collections);
  }
  async writeToDisk(filePath) {
    if (!this.#dirty) {
      return;
    }
    try {
      await fs.writeFile(filePath, this.toString());
      this.#file = filePath;
      this.#dirty = false;
    } catch (err) {
      throw new AstroError(AstroErrorData.UnknownFilesystemError, { cause: err });
    }
  }
  /**
   * Attempts to load a MutableDataStore from the virtual module.
   * This only works in Vite.
   */
  static async fromModule() {
    try {
      const data = await import("astro:data-layer-content");
      const map = devalue.unflatten(data.default);
      return MutableDataStore.fromMap(map);
    } catch {
    }
    return new MutableDataStore();
  }
  static async fromMap(data) {
    const store = new MutableDataStore();
    store._collections = data;
    return store;
  }
  static async fromString(data) {
    const map = devalue.parse(data);
    return MutableDataStore.fromMap(map);
  }
  static async fromFile(filePath) {
    try {
      if (existsSync(filePath)) {
        const data = await fs.readFile(filePath, "utf-8");
        return MutableDataStore.fromString(data);
      }
    } catch {
    }
    return new MutableDataStore();
  }
}
export {
  MutableDataStore
};
