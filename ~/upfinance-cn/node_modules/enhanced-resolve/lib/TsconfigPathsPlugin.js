/*
	MIT License http://www.opensource.org/licenses/mit-license.php
	Author Natsu @xiaoxiaojx
*/

"use strict";

const { aliasResolveHandler } = require("./AliasUtils");
const { modulesResolveHandler } = require("./ModulesUtils");
const { readJson } = require("./util/fs");
const {
	PathType: _PathType,
	cachedDirname: dirname,
	cachedJoin: join,
	isSubPath,
	normalize,
} = require("./util/path");

/** @typedef {import("./Resolver")} Resolver */
/** @typedef {import("./Resolver").ResolveStepHook} ResolveStepHook */
/** @typedef {import("./AliasUtils").AliasOption} AliasOption */
/** @typedef {import("./Resolver").ResolveRequest} ResolveRequest */
/** @typedef {import("./Resolver").ResolveContext} ResolveContext */
/** @typedef {import("./Resolver").FileSystem} FileSystem */
/** @typedef {import("./Resolver").TsconfigPathsData} TsconfigPathsData */
/** @typedef {import("./Resolver").TsconfigPathsMap} TsconfigPathsMap */
/** @typedef {import("./ResolverFactory").TsconfigOptions} TsconfigOptions */

/**
 * @typedef {object} TsconfigCompilerOptions
 * @property {string=} baseUrl Base URL for resolving paths
 * @property {{ [key: string]: string[] }=} paths TypeScript paths mapping
 */

/**
 * @typedef {object} TsconfigReference
 * @property {string} path Path to the referenced project
 */

/**
 * @typedef {object} Tsconfig
 * @property {TsconfigCompilerOptions=} compilerOptions Compiler options
 * @property {string | string[]=} extends Extended configuration paths
 * @property {TsconfigReference[]=} references Project references
 */

const DEFAULT_CONFIG_FILE = "tsconfig.json";

/**
 * @param {string} pattern Path pattern
 * @returns {number} Length of the prefix
 */
function getPrefixLength(pattern) {
	const prefixLength = pattern.indexOf("*");
	if (prefixLength === -1) {
		return pattern.length;
	}
	return pattern.slice(0, Math.max(0, prefixLength)).length;
}

/**
 * Sort path patterns.
 * If a module name can be matched with multiple patterns then pattern with the longest prefix will be picked.
 * @param {string[]} arr Array of path patterns
 * @returns {string[]} Array of path patterns sorted by longest prefix
 */
function sortByLongestPrefix(arr) {
	return [...arr].sort((a, b) => getPrefixLength(b) - getPrefixLength(a));
}

/**
 * Merge two tsconfig objects
 * @param {Tsconfig | null} base base config
 * @param {Tsconfig | null} config config to merge
 * @returns {Tsconfig} merged config
 */
function mergeTsconfigs(base, config) {
	base = base || {};
	config = config || {};

	return {
		...base,
		...config,
		compilerOptions: {
			.../** @type {TsconfigCompilerOptions} */ (base.compilerOptions),
			.../** @type {TsconfigCompilerOptions} */ (config.compilerOptions),
		},
	};
}

/**
 * Substitute ${configDir} template variable in path
 * @param {string} pathValue the path value
 * @param {string} configDir the config directory
 * @returns {string} the path with substituted template
 */
function substituteConfigDir(pathValue, configDir) {
	return pathValue.replace(/\$\{configDir\}/g, configDir);
}

/**
 * Convert tsconfig paths to resolver options
 * @param {string} configDir Config file directory
 * @param {{ [key: string]: string[] }} paths TypeScript paths mapping
 * @param {string=} baseUrl Base URL for resolving paths (relative to configDir)
 * @returns {TsconfigPathsData} the resolver options
 */
function tsconfigPathsToResolveOptions(configDir, paths, baseUrl) {
	// Calculate absolute base URL
	const absoluteBaseUrl = !baseUrl ? configDir : join(configDir, baseUrl);

	/** @type {string[]} */
	const sortedKeys = sortByLongestPrefix(Object.keys(paths));
	/** @type {AliasOption[]} */
	const alias = [];
	/** @type {string[]} */
	const modules = [];

	for (const pattern of sortedKeys) {
		const mappings = paths[pattern];
		// Substitute ${configDir} in path mappings
		const absolutePaths = mappings.map((mapping) => {
			const substituted = substituteConfigDir(mapping, configDir);
			return join(absoluteBaseUrl, substituted);
		});

		if (absolutePaths.length > 0) {
			if (pattern === "*") {
				modules.push(
					...absolutePaths
						.map((dir) => {
							if (/[/\\]\*$/.test(dir)) {
								return dir.replace(/[/\\]\*$/, "");
							}
							return "";
						})
						.filter(Boolean),
				);
			} else {
				alias.push({ name: pattern, alias: absolutePaths });
			}
		}
	}

	if (absoluteBaseUrl && !modules.includes(absoluteBaseUrl)) {
		modules.push(absoluteBaseUrl);
	}

	return {
		alias,
		modules,
	};
}

/**
 * Get the base context for the current project
 * @param {string} context the context
 * @param {string=} baseUrl base URL for resolving paths
 * @returns {string} the base context
 */
function getAbsoluteBaseUrl(context, baseUrl) {
	return !baseUrl ? context : join(context, baseUrl);
}

module.exports = class TsconfigPathsPlugin {
	/**
	 * @param {true | string | TsconfigOptions} configFileOrOptions tsconfig file path or options object
	 */
	constructor(configFileOrOptions) {
		if (
			typeof configFileOrOptions === "object" &&
			configFileOrOptions !== null
		) {
			// Options object format
			this.configFile = configFileOrOptions.configFile || DEFAULT_CONFIG_FILE;
			/** @type {string[] | "auto"} */
			if (Array.isArray(configFileOrOptions.references)) {
				/** @type {TsconfigReference[] | "auto"} */
				this.references = configFileOrOptions.references.map((ref) => ({
					path: ref,
				}));
			} else if (configFileOrOptions.references === "auto") {
				this.references = "auto";
			} else {
				this.references = [];
			}
		} else {
			this.configFile =
				configFileOrOptions === true
					? DEFAULT_CONFIG_FILE
					: /** @type {string} */ (configFileOrOptions);
			/** @type {TsconfigReference[] | "auto"} */
			this.references = [];
		}
	}

	/**
	 * @param {Resolver} resolver the resolver
	 * @returns {void}
	 */
	apply(resolver) {
		const aliasTarget = resolver.ensureHook("internal-resolve");
		const moduleTarget = resolver.ensureHook("module");

		resolver
			.getHook("raw-resolve")
			.tapAsync(
				"TsconfigPathsPlugin",
				async (request, resolveContext, callback) => {
					try {
						const tsconfigPathsMap = await this._getTsconfigPathsMap(
							resolver,
							request,
							resolveContext,
						);

						if (!tsconfigPathsMap) return callback();

						const selectedData = this._selectPathsDataForContext(
							request.path,
							tsconfigPathsMap,
						);

						if (!selectedData) return callback();

						aliasResolveHandler(
							resolver,
							selectedData.alias,
							aliasTarget,
							request,
							resolveContext,
							callback,
						);
					} catch (err) {
						callback(/** @type {Error} */ (err));
					}
				},
			);

		resolver
			.getHook("raw-module")
			.tapAsync(
				"TsconfigPathsPlugin",
				async (request, resolveContext, callback) => {
					try {
						const tsconfigPathsMap = await this._getTsconfigPathsMap(
							resolver,
							request,
							resolveContext,
						);

						if (!tsconfigPathsMap) return callback();

						const selectedData = this._selectPathsDataForContext(
							request.path,
							tsconfigPathsMap,
						);

						if (!selectedData) return callback();

						modulesResolveHandler(
							resolver,
							selectedData.modules,
							moduleTarget,
							request,
							resolveContext,
							callback,
						);
					} catch (err) {
						callback(/** @type {Error} */ (err));
					}
				},
			);
	}

	/**
	 * Get TsconfigPathsMap for the request (with caching)
	 * @param {Resolver} resolver the resolver
	 * @param {ResolveRequest} request the request
	 * @param {ResolveContext} resolveContext the resolve context
	 * @returns {Promise<TsconfigPathsMap | null>} the tsconfig paths map or null
	 */
	async _getTsconfigPathsMap(resolver, request, resolveContext) {
		if (typeof request.tsconfigPathsMap === "undefined") {
			try {
				const absTsconfigPath = join(
					request.path || process.cwd(),
					this.configFile,
				);
				const result = await this._loadTsconfigPathsMap(
					resolver.fileSystem,
					absTsconfigPath,
				);

				request.tsconfigPathsMap = result;
			} catch (err) {
				request.tsconfigPathsMap = null;
				throw err;
			}
		}

		if (!request.tsconfigPathsMap) {
			return null;
		}

		for (const fileDependency of request.tsconfigPathsMap.fileDependencies) {
			if (resolveContext.fileDependencies) {
				resolveContext.fileDependencies.add(fileDependency);
			}
		}
		return request.tsconfigPathsMap;
	}

	/**
	 * Load tsconfig.json and build complete TsconfigPathsMap
	 * Includes main project paths and all referenced projects
	 * @param {FileSystem} fileSystem the file system
	 * @param {string} absTsconfigPath absolute path to tsconfig.json
	 * @returns {Promise<TsconfigPathsMap>} the complete tsconfig paths map
	 */
	async _loadTsconfigPathsMap(fileSystem, absTsconfigPath) {
		/** @type {Set<string>} */
		const fileDependencies = new Set();
		const config = await this._loadTsconfig(
			fileSystem,
			absTsconfigPath,
			fileDependencies,
		);

		const compilerOptions = config.compilerOptions || {};
		const mainContext = dirname(absTsconfigPath);

		const main = tsconfigPathsToResolveOptions(
			mainContext,
			compilerOptions.paths || {},
			compilerOptions.baseUrl,
		);
		/** @type {{ [baseUrl: string]: TsconfigPathsData }} */
		const refs = {};

		let referencesToUse = null;
		if (this.references === "auto") {
			referencesToUse = config.references;
		} else if (Array.isArray(this.references)) {
			referencesToUse = this.references;
		}

		if (Array.isArray(referencesToUse)) {
			await this._loadTsconfigReferences(
				fileSystem,
				mainContext,
				referencesToUse,
				fileDependencies,
				refs,
			);
		}

		return { main, mainContext, refs, fileDependencies };
	}

	/**
	 * Select the correct TsconfigPathsData based on request.path (context-aware)
	 * Matches the behavior of tsconfig-paths-webpack-plugin
	 * @param {string | false} requestPath the request path
	 * @param {TsconfigPathsMap} tsconfigPathsMap the tsconfig paths map
	 * @returns {TsconfigPathsData | null} the selected paths data
	 */
	_selectPathsDataForContext(requestPath, tsconfigPathsMap) {
		const { main, mainContext, refs } = tsconfigPathsMap;
		if (!requestPath) {
			return main;
		}

		// Combine main and refs into a single map: context path -> TsconfigPathsData
		const allContexts = {
			[mainContext]: main,
			...refs,
		};

		let longestMatch = null;
		let longestMatchLength = 0;

		for (const [context, data] of Object.entries(allContexts)) {
			if (context === requestPath) {
				return data;
			}
			if (
				isSubPath(context, requestPath) &&
				context.length > longestMatchLength
			) {
				longestMatch = data;
				longestMatchLength = context.length;
			}
		}

		if (longestMatch) {
			return longestMatch;
		}

		return null;
	}

	/**
	 * Load tsconfig from extends path
	 * @param {FileSystem} fileSystem the file system
	 * @param {string} configFilePath current config file path
	 * @param {string} extendedConfigValue extends value
	 * @param {Set<string>} fileDependencies the file dependencies
	 * @returns {Promise<Tsconfig>} the extended tsconfig
	 */
	async _loadTsconfigFromExtends(
		fileSystem,
		configFilePath,
		extendedConfigValue,
		fileDependencies,
	) {
		const currentDir = dirname(configFilePath);

		// Substitute ${configDir} in extends path
		extendedConfigValue = substituteConfigDir(extendedConfigValue, currentDir);

		if (
			typeof extendedConfigValue === "string" &&
			!extendedConfigValue.includes(".json")
		) {
			extendedConfigValue += ".json";
		}

		let extendedConfigPath = join(currentDir, extendedConfigValue);

		const exists = await new Promise((resolve) => {
			fileSystem.readFile(extendedConfigPath, (err) => {
				resolve(!err);
			});
		});
		if (!exists && extendedConfigValue.includes("/")) {
			extendedConfigPath = join(
				currentDir,
				normalize(`node_modules/${extendedConfigValue}`),
			);
		}

		const config = await this._loadTsconfig(
			fileSystem,
			extendedConfigPath,
			fileDependencies,
		);
		const compilerOptions = config.compilerOptions || { baseUrl: undefined };

		if (compilerOptions.baseUrl) {
			const extendsDir = dirname(extendedConfigValue);
			compilerOptions.baseUrl = getAbsoluteBaseUrl(
				extendsDir,
				compilerOptions.baseUrl,
			);
		}

		delete config.references;

		return /** @type {Tsconfig} */ (config);
	}

	/**
	 * Load referenced tsconfig projects and store in referenceMatchMap
	 * Simple implementation matching tsconfig-paths-webpack-plugin:
	 * Just load each reference and store independently
	 * @param {FileSystem} fileSystem the file system
	 * @param {string} context the context
	 * @param {TsconfigReference[]} references array of references
	 * @param {Set<string>} fileDependencies the file dependencies
	 * @param {{ [baseUrl: string]: TsconfigPathsData }} referenceMatchMap the map to populate
	 * @returns {Promise<void>}
	 */
	async _loadTsconfigReferences(
		fileSystem,
		context,
		references,
		fileDependencies,
		referenceMatchMap,
	) {
		for (const ref of references) {
			// Substitute ${configDir} in reference path
			const refPath = substituteConfigDir(ref.path, context);
			const refConfigPath = join(join(context, refPath), DEFAULT_CONFIG_FILE);

			try {
				const refConfig = await this._loadTsconfig(
					fileSystem,
					refConfigPath,
					fileDependencies,
				);

				if (refConfig.compilerOptions && refConfig.compilerOptions.paths) {
					const refContext = dirname(refConfigPath);

					referenceMatchMap[refContext] = tsconfigPathsToResolveOptions(
						refContext,
						refConfig.compilerOptions.paths || {},
						refConfig.compilerOptions.baseUrl,
					);
				}

				if (this.references === "auto" && Array.isArray(refConfig.references)) {
					await this._loadTsconfigReferences(
						fileSystem,
						dirname(refConfigPath),
						refConfig.references,
						fileDependencies,
						referenceMatchMap,
					);
				}
			} catch (_err) {
				continue;
			}
		}
	}

	/**
	 * Load tsconfig.json with extends support
	 * @param {FileSystem} fileSystem the file system
	 * @param {string} configFilePath absolute path to tsconfig.json
	 * @param {Set<string>} fileDependencies the file dependencies
	 * @returns {Promise<Tsconfig>} the merged tsconfig
	 */
	async _loadTsconfig(fileSystem, configFilePath, fileDependencies) {
		const config = await readJson(fileSystem, configFilePath);
		fileDependencies.add(configFilePath);

		let result = config;

		const extendedConfig = config.extends;
		if (extendedConfig) {
			let base;

			if (Array.isArray(extendedConfig)) {
				base = {};
				for (const extendedConfigElement of extendedConfig) {
					const extendedTsconfig = await this._loadTsconfigFromExtends(
						fileSystem,
						configFilePath,
						extendedConfigElement,
						fileDependencies,
					);
					base = mergeTsconfigs(base, extendedTsconfig);
				}
			} else {
				base = await this._loadTsconfigFromExtends(
					fileSystem,
					configFilePath,
					extendedConfig,
					fileDependencies,
				);
			}

			result = /** @type {Tsconfig} */ (mergeTsconfigs(base, config));
		}

		return result;
	}
};
