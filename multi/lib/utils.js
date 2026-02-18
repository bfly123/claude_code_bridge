"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.getProjectInfo = getProjectInfo;
exports.getInstancesDir = getInstancesDir;
exports.getInstanceDir = getInstanceDir;
exports.listInstances = listInstances;
exports.isInstanceRunning = isInstanceRunning;
const path = __importStar(require("path"));
const fs = __importStar(require("fs"));
const crypto_1 = require("crypto");
function _shortProjectHash(projectRoot) {
    return (0, crypto_1.createHash)('sha256').update(projectRoot).digest('hex').slice(0, 8);
}
function getProjectInfo() {
    const root = process.cwd();
    const name = path.basename(root);
    return { root, name };
}
function getInstancesDir(projectRoot) {
    return path.join(projectRoot, '.ccb-instances');
}
function getInstanceDir(projectRoot, instanceId) {
    const hash = _shortProjectHash(projectRoot);
    const newDir = path.join(getInstancesDir(projectRoot), `inst-${hash}-${instanceId}`);
    // Backward compat: if new dir doesn't exist but old format does, use old
    if (!fs.existsSync(newDir)) {
        const oldDir = path.join(getInstancesDir(projectRoot), `instance-${instanceId}`);
        if (fs.existsSync(oldDir)) {
            return oldDir;
        }
    }
    return newDir;
}
function listInstances(projectRoot) {
    const instancesDir = getInstancesDir(projectRoot);
    if (!fs.existsSync(instancesDir)) {
        return [];
    }
    const hash = _shortProjectHash(projectRoot);
    const newPrefix = `inst-${hash}-`;
    return fs.readdirSync(instancesDir)
        .filter(name => name.startsWith(newPrefix) || name.startsWith('instance-'))
        .map(name => {
            if (name.startsWith(newPrefix)) return name.slice(newPrefix.length);
            return name.replace('instance-', '');
        })
        .sort((a, b) => parseInt(a) - parseInt(b));
}
function isInstanceRunning(projectRoot, instanceId) {
    const instanceDir = getInstanceDir(projectRoot, instanceId);
    const ccbDir = path.join(instanceDir, '.ccb');
    if (!fs.existsSync(ccbDir)) {
        return false;
    }
    // Check for session files
    const sessionFiles = fs.readdirSync(ccbDir)
        .filter(name => name.endsWith('-session'));
    return sessionFiles.length > 0;
}
//# sourceMappingURL=utils.js.map