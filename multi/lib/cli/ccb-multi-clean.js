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
const commander_1 = require("commander");
const program = new commander_1.Command();
program
    .name('ccb-multi-clean')
    .description('Clean up CCB multi-instance directories')
    .option('-f, --force', 'Force clean without confirmation')
    .action(async (options) => {
    try {
        const projectInfo = (0, utils_1.getProjectInfo)();
        const instancesDir = (0, utils_1.getInstancesDir)(projectInfo.root);
        console.log('');
        console.log(chalk_1.default.cyan('    ██████╗ ██████╗██████╗       ███╗   ███╗██╗   ██╗██╗  ████████╗██╗'));
        console.log(chalk_1.default.cyan('   ██╔════╝██╔════╝██╔══██╗      ████╗ ████║██║   ██║██║  ╚══██╔══╝██║'));
        console.log(chalk_1.default.cyan('   ██║     ██║     ██████╔╝█████╗██╔████╔██║██║   ██║██║     ██║   ██║'));
        console.log(chalk_1.default.cyan('   ██║     ██║     ██╔══██╗╚════╝██║╚██╔╝██║██║   ██║██║     ██║   ██║'));
        console.log(chalk_1.default.cyan('   ╚██████╗╚██████╗██████╔╝      ██║ ╚═╝ ██║╚██████╔╝███████╗██║   ██║'));
        console.log(chalk_1.default.cyan('    ╚═════╝ ╚═════╝╚═════╝       ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝   ╚═╝'));
        console.log('');
        console.log('  Multi-Instance Cleanup');
        console.log('');
        if (!fs.existsSync(instancesDir)) {
            console.log(chalk_1.default.dim('  No instances directory found'));
            return;
        }
        const instances = fs.readdirSync(instancesDir)
            .filter(name => name.startsWith('inst-') || name.startsWith('instance-'));
        if (instances.length === 0) {
            console.log(chalk_1.default.dim('  No instances to clean'));
            return;
        }
        console.log(chalk_1.default.dim(`  Found ${instances.length} instance(s) to remove:`));
        console.log('');
        instances.forEach(name => {
            console.log(chalk_1.default.dim(`    ${name}`));
        });
        console.log('');
        if (!options.force) {
            console.log(chalk_1.default.yellow('  Warning: This will delete all instance directories'));
            console.log(chalk_1.default.dim('  (shared history will be preserved)'));
            console.log('');
            console.log(chalk_1.default.dim('  Run with --force to confirm'));
            console.log('');
            return;
        }
        // Clean up instances
        for (const instance of instances) {
            const instancePath = path.join(instancesDir, instance);
            fs.rmSync(instancePath, { recursive: true, force: true });
            console.log(chalk_1.default.green(`  ✓ Removed ${instance}`));
        }
        console.log('');
        console.log(chalk_1.default.green('  Cleanup complete'));
        console.log('');
    }
    catch (error) {
        console.error(chalk_1.default.red('  ✗ Error:'), error instanceof Error ? error.message : error);
        process.exit(1);
    }
});
program.parse();
//# sourceMappingURL=ccb-multi-clean.js.map