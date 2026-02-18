/**
 * Creates a CryptoKey object that can be used to encrypt any string.
 */
export declare function createKey(): Promise<CryptoKey>;
/**
 * Get the encoded value of the ASTRO_KEY env var.
 */
export declare function getEncodedEnvironmentKey(): string;
/**
 * See if the environment variable key ASTRO_KEY is set.
 */
export declare function hasEnvironmentKey(): boolean;
/**
 * Get the environment variable key and decode it into a CryptoKey.
 */
export declare function getEnvironmentKey(): Promise<CryptoKey>;
/**
 * Takes a key that has been serialized to an array of bytes and returns a CryptoKey
 */
export declare function importKey(bytes: Uint8Array): Promise<CryptoKey>;
/**
 * Encodes a CryptoKey to base64 string, so that it can be embedded in JSON / JavaScript
 */
export declare function encodeKey(key: CryptoKey): Promise<string>;
/**
 * Decodes a base64 string into bytes and then imports the key.
 */
export declare function decodeKey(encoded: string): Promise<CryptoKey>;
/**
 * Using a CryptoKey, encrypt a string into a base64 string.
 */
export declare function encryptString(key: CryptoKey, raw: string): Promise<string>;
/**
 * Takes a base64 encoded string, decodes it and returns the decrypted text.
 */
export declare function decryptString(key: CryptoKey, encoded: string): Promise<string>;
