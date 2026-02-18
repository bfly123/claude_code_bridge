export type MarkdownImagePath = {
    raw: string;
    safeName: string;
};
export declare function getMarkdownCodeForImages(imagePaths: MarkdownImagePath[], html: string): string;
