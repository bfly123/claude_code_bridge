/*
	MIT License http://www.opensource.org/licenses/mit-license.php
	Author Natsu @xiaoxiaojx
*/

"use strict";

/** @typedef {import("../Resolver").FileSystem} FileSystem */

/**
 * Read and parse JSON file
 * @template T
 * @param {FileSystem} fileSystem the file system
 * @param {string} jsonFilePath absolute path to JSON file
 * @returns {Promise<T>} parsed JSON content
 */
async function readJson(fileSystem, jsonFilePath) {
	const { readJson } = fileSystem;
	if (readJson) {
		return new Promise((resolve, reject) => {
			readJson(jsonFilePath, (err, content) => {
				if (err) return reject(err);
				resolve(/** @type {T} */ (content));
			});
		});
	}

	const buf = await new Promise((resolve, reject) => {
		fileSystem.readFile(jsonFilePath, (err, data) => {
			if (err) return reject(err);
			resolve(data);
		});
	});

	return JSON.parse(/** @type {string} */ (buf.toString()));
}

module.exports.readJson = readJson;
