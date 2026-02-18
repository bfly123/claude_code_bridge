declare function whichpm (pkgPath: string): Promise<whichpm.Result | null>

declare namespace whichpm {
  type Result = NPM | YARN | PNPM | BUN | Other

  interface NPM {
    readonly name: 'npm'
  }

  interface YARN {
    readonly name: 'yarn'
  }

  interface PNPM {
    readonly name: 'pnpm'
    readonly version: string
  }

  interface BUN {
    readonly name: 'bun'
  }

  interface Other {
    readonly name: string
    readonly version?: string
  }
}

export = whichpm
