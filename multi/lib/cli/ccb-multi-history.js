#!/usr/bin/env node
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
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const chalk_1 = __importDefault(require("chalk"));
const utils_1 = require("../utils");
async function main() {
    try {
        const projectInfo = (0, utils_1.getProjectInfo)();
        const historyDir = path.join(projectInfo.root, '.ccb', 'history');
        console.log('');
        console.log(chalk_1.default.cyan('    ██████╗ ██████╗██████╗       ███╗   ███╗██╗   ██╗██╗  ████████╗██╗'));
        console.log(chalk_1.default.cyan('   ██╔════╝██╔════╝██╔══██╗      ████╗ ████║██║   ██║██║  ╚══██╔══╝██║'));
        console.log(chalk_1.default.cyan('   ██║     ██║     ██████╔╝█████╗██╔████╔██║██║   ██║██║     ██║   ██║'));
        console.log(chalk_1.default.cyan('   ██║     ██║     ██╔══██╗╚════╝██║╚██╔╝██║██║   ██║██║     ██║   ██║'));
        console.log(chalk_1.default.cyan('   ╚██████╗╚██████╗██████╔╝      ██║ ╚═╝ ██║╚██████╔╝███████╗██║   ██║'));
        console.log(chalk_1.default.cyan('    ╚═════╝ ╚═════╝╚═════╝       ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝   ╚═╝'));
        console.log('');
        console.log('  Session History');
        console.log('');
        if (!fs.existsSync(historyDir)) {
            console.log(chalk_1.default.dim('  No history directory found'));
            return;
        }
        console.log(chalk_1.default.dim('  RECENT SESSIONS (shared across all instances)'));
        console.log('');
        // List recent history files
        const files = fs.readdirSync(historyDir)
            .filter(name => name.endsWith('.md'))
            .map(name => ({
            name,
            path: path.join(historyDir, name),
            stat: fs.statSync(path.join(historyDir, name))
        }))
            .sort((a, b) => b.stat.mtimeMs - a.stat.mtimeMs)
            .slice(0, 10);
        if (files.length === 0) {
            console.log(chalk_1.default.dim('  No session history found'));
            return;
        }
        for (const file of files) {
            const provider = file.name.split('-')[0];
            const size = (file.stat.size / 1024).toFixed(1) + 'K';
            const time = file.stat.mtime.toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
            console.log(`    ${chalk_1.default.cyan(provider.padEnd(8))}  ${chalk_1.default.dim(size.padEnd(8))}  ${chalk_1.default.dim(time)}`);
        }
        console.log('');
        console.log(chalk_1.default.dim(`    History location: ${historyDir}`));
        console.log('');
    }
    catch (error) {
        console.error(chalk_1.default.red('  ✗ Error:'), error instanceof Error ? error.message : error);
        process.exit(1);
    }
}
main();
//# sourceMappingURL=ccb-multi-history.js.map