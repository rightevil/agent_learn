import chalk from "chalk";

export const logger = {
  info(msg: string) {
    console.log(chalk.blue("[DevPilot]"), msg);
  },
  success(msg: string) {
    console.log(chalk.green("[DevPilot]"), msg);
  },
  warn(msg: string) {
    console.log(chalk.yellow("[DevPilot]"), msg);
  },
  error(msg: string) {
    console.error(chalk.red("[DevPilot]"), msg);
  },
  agent(name: string, msg: string) {
    console.log(chalk.cyan(`[${name}]`), msg);
  },
  tool(name: string, msg: string) {
    console.log(chalk.magenta(`[${name}]`), msg);
  },
};
