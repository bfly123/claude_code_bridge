export type RemoteCacheEntry = {
    data: string;
    expires: number;
};
export declare function loadRemoteImage(src: string): Promise<{
    data: Buffer;
    expires: number;
}>;
