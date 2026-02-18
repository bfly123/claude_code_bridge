#!/usr/bin/env node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const commander_1 = require("commander");
const instance_1 = require("../instance");
const utils_1 = require("../utils");
const chalk_1 = __importDefault(require("chalk"));
const program = new commander_1.Command();
program
    .name('ccb-multi')
    .description('Multi-instance manager for CCB (Claude Code Bridge)')
    .version('1.0.0')
    .argument('<instance-id>', 'Instance ID (1, 2, 3, ...)')
    .argument('[providers...]', 'AI providers (e.g., codex gemini claude)')
    .action(async (instanceId, providers) => {
    try {
        const projectInfo = (0, utils_1.getProjectInfo)();
        console.log('');
        console.log(chalk_1.default.cyan('    ██████╗ ██████╗██████╗       ███╗   ███╗██╗   ██╗██╗  ████████╗██╗'));
        console.log(chalk_1.default.cyan('   ██╔════╝██╔════╝██╔══██╗      ████╗ ████║██║   ██║██║  ╚══██╔══╝██║'));
        console.log(chalk_1.default.cyan('   ██║     ██║     ██████╔╝█████╗██╔████╔██║██║   ██║██║     ██║   ██║'));
        console.log(chalk_1.default.cyan('   ██║     ██║     ██╔══██╗╚════╝██║╚██╔╝██║██║   ██║██║     ██║   ██║'));
        console.log(chalk_1.default.cyan('   ╚██████╗╚██████╗██████╔╝      ██║ ╚═╝ ██║╚██████╔╝███████╗██║   ██║'));
        console.log(chalk_1.default.cyan('    ╚═════╝ ╚═════╝╚═════╝       ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝   ╚═╝'));
        console.log('');
        console.log('  Multi-Instance Manager for Claude Code Bridge');
        console.log('');
        console.log(chalk_1.default.dim(`    Project     ${projectInfo.name}`));
        console.log(chalk_1.default.dim(`    Instance    ${instanceId}`));
        if (providers.length > 0) {
            console.log(chalk_1.default.dim(`    Providers   ${providers.join(', ')}`));
        }
        console.log('');
        await (0, instance_1.startInstance)(instanceId, providers, projectInfo);
    }
    catch (error) {
        console.error(chalk_1.default.red('  ✗ Error:'), error instanceof Error ? error.message : error);
        process.exit(1);
    }
});
program.parse();
//# sourceMappingURL=ccb-multi.js.map