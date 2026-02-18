#!/usr/bin/env node
"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const chalk_1 = __importDefault(require("chalk"));
const utils_1 = require("../utils");
async function main() {
    try {
        const projectInfo = (0, utils_1.getProjectInfo)();
        const instances = (0, utils_1.listInstances)(projectInfo.root);
        console.log('');
        console.log(chalk_1.default.cyan('    ██████╗ ██████╗██████╗       ███╗   ███╗██╗   ██╗██╗  ████████╗██╗'));
        console.log(chalk_1.default.cyan('   ██╔════╝██╔════╝██╔══██╗      ████╗ ████║██║   ██║██║  ╚══██╔══╝██║'));
        console.log(chalk_1.default.cyan('   ██║     ██║     ██████╔╝█████╗██╔████╔██║██║   ██║██║     ██║   ██║'));
        console.log(chalk_1.default.cyan('   ██║     ██║     ██╔══██╗╚════╝██║╚██╔╝██║██║   ██║██║     ██║   ██║'));
        console.log(chalk_1.default.cyan('   ╚██████╗╚██████╗██████╔╝      ██║ ╚═╝ ██║╚██████╔╝███████╗██║   ██║'));
        console.log(chalk_1.default.cyan('    ╚═════╝ ╚═════╝╚═════╝       ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝   ╚═╝'));
        console.log('');
        console.log('  Multi-Instance Status');
        console.log('');
        if (instances.length === 0) {
            console.log(chalk_1.default.dim('    No instances found'));
            return;
        }
        let runningCount = 0;
        let stoppedCount = 0;
        console.log(chalk_1.default.dim('  INSTANCES'));
        console.log('');
        for (const instanceId of instances) {
            const running = (0, utils_1.isInstanceRunning)(projectInfo.root, instanceId);
            if (running) {
                console.log(`  ${chalk_1.default.green('●')} Instance ${instanceId}  ${chalk_1.default.dim('running')}`);
                runningCount++;
            }
            else {
                console.log(`  ${chalk_1.default.dim('○')} Instance ${instanceId}  ${chalk_1.default.dim('stopped')}`);
                stoppedCount++;
            }
        }
        console.log('');
        console.log(chalk_1.default.dim('  SUMMARY'));
        console.log('');
        console.log(`    Total      ${instances.length}`);
        console.log(`    Running    ${chalk_1.default.green(runningCount.toString())}`);
        console.log(`    Stopped    ${chalk_1.default.dim(stoppedCount.toString())}`);
        console.log('');
    }
    catch (error) {
        console.error(chalk_1.default.red('  ✗ Error:'), error instanceof Error ? error.message : error);
        process.exit(1);
    }
}
main();
//# sourceMappingURL=ccb-multi-status.js.map