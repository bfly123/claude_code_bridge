export = preferredPM

declare function preferredPM (pkgPath: string): Promise<{ name: 'npm' | 'pnpm' | 'yarn' | 'bun', version: string } | null>
