'use strict'
const findYarnWorkspaceRoot = require('find-yarn-workspace-root2')
const fs = require('fs')
const path = require('path')
const whichPM = require('which-pm')

module.exports = async function preferredPM (pkgPath) {
  if (typeof pkgPath !== 'string') {
    throw new TypeError(`pkgPath should be a string, got ${typeof pkgPath}`)
  }
  if (fs.existsSync(path.join(pkgPath, 'package-lock.json'))) {
    return {
      name: 'npm',
      version: '>=5'
    }
  }
  if (fs.existsSync(path.join(pkgPath, 'yarn.lock'))) {
    return {
      name: 'yarn',
      version: '*'
    }
  }
  if (fs.existsSync(path.join(pkgPath, 'pnpm-lock.yaml'))) {
    return {
      name: 'pnpm',
      version: '>=3'
    }
  }
  if (fs.existsSync(path.join(pkgPath, 'shrinkwrap.yaml'))) {
    return {
      name: 'pnpm',
      version: '1 || 2'
    }
  }
  if (fs.existsSync(path.join(pkgPath, 'bun.lockb')) || fs.existsSync(path.join(pkgPath, 'bun.lock'))) {
    return {
      name: 'bun',
      version: '*'
    }
  }
  const { findUp } = await import('find-up-simple')
  if (await findUp('pnpm-lock.yaml', { cwd: pkgPath })) {
    return {
      name: 'pnpm',
      version: '>=3'
    }
  }
  try {
    const workspaceRoot = findYarnWorkspaceRoot(pkgPath)
    if (typeof workspaceRoot === 'string') {
      if (fs.existsSync(path.join(workspaceRoot, 'package-lock.json'))) {
        return {
          name: 'npm',
          version: '>=7'
        }
      }
      return {
        name: 'yarn',
        version: '*'
      }
    }
  } catch (err) {}
  const pm = await whichPM(pkgPath)
  return pm && { name: pm.name, version: pm.version || '*' }
}
