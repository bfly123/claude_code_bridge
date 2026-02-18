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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.startInstance = startInstance;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const child_process_1 = require("child_process");
const chalk_1 = __importDefault(require("chalk"));
const crypto_1 = require("crypto");
function _shortProjectHash(projectRoot) {
    // Generate a short (8-char) hash from project root path to avoid
    // basename collisions across projects in Gemini CLI 0.29.0.
    return (0, crypto_1.createHash)('sha256').update(projectRoot).digest('hex').slice(0, 8);
}
async function startInstance(instanceId, providers, projectInfo) {
    const projectHash = _shortProjectHash(projectInfo.root);
    const instanceDir = path.join(projectInfo.root, '.ccb-instances', `inst-${projectHash}-${instanceId}`);
    const ccbDir = path.join(instanceDir, '.ccb');
    // Create instance directory
    fs.mkdirSync(instanceDir, { recursive: true });
    fs.mkdirSync(ccbDir, { recursive: true });
    // Ensure main project .ccb directory exists
    const mainCcbDir = path.join(projectInfo.root, '.ccb');
    const mainHistoryDir = path.join(mainCcbDir, 'history');
    fs.mkdirSync(mainHistoryDir, { recursive: true });
    console.log(chalk_1.default.dim('    Creating symlinks...'));
    // Create symlinks for project files (excluding .ccb-instances and .ccb)
    const excludeDirs = ['.ccb-instances', '.ccb', '.claude', '.opencode', 'node_modules', '.git'];
    const items = fs.readdirSync(projectInfo.root);
    for (const item of items) {
        if (excludeDirs.includes(item))
            continue;
        const sourcePath = path.join(projectInfo.root, item);
        const targetPath = path.join(instanceDir, item);
        try {
            // Remove existing symlink if exists
            if (fs.existsSync(targetPath)) {
                fs.unlinkSync(targetPath);
            }
            fs.symlinkSync(sourcePath, targetPath);
        }
        catch (error) {
            // Ignore symlink errors
        }
    }
    // Create symlinks for shared history and config
    const historySymlink = path.join(ccbDir, 'history');
    const configSymlink = path.join(ccbDir, 'ccb.config');
    if (fs.existsSync(historySymlink)) {
        fs.unlinkSync(historySymlink);
    }
    fs.symlinkSync(mainHistoryDir, historySymlink);
    const mainConfigPath = path.join(mainCcbDir, 'ccb.config');
    if (fs.existsSync(mainConfigPath)) {
        if (fs.existsSync(configSymlink)) {
            fs.unlinkSync(configSymlink);
        }
        fs.symlinkSync(mainConfigPath, configSymlink);
    }
    // Write config if providers specified
    if (providers.length > 0) {
        const configContent = providers.join(',');
        fs.writeFileSync(path.join(ccbDir, 'ccb.config'), configContent);
    }
    // Set environment variables
    process.env.CCB_INSTANCE_ID = instanceId;
    process.env.CCB_PROJECT_ROOT = projectInfo.root;
    console.log(chalk_1.default.green('  ✓ Instance ready'));
    console.log('');
    console.log(chalk_1.default.dim('    Launching CCB...'));
    console.log('');
    const ccb = (0, child_process_1.spawn)('ccb', [], {
        cwd: instanceDir,
        stdio: 'inherit',
        env: process.env
    });
    ccb.on('error', (error) => {
        console.error(chalk_1.default.red('  ✗ Failed to launch CCB:'), error.message);
        process.exit(1);
    });
    ccb.on('exit', (code) => {
        if (code !== 0) {
            console.error(chalk_1.default.red(`  ✗ CCB exited with code ${code}`));
            process.exit(code || 1);
        }
    });
}
//# sourceMappingURL=instance.js.map