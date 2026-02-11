const chalk = require('chalk');

// 显示菜单
function displayMenu(title, options) {
  console.log(chalk.cyan.bold(`\n${title}\n`));
  options.forEach((opt, index) => {
    console.log(`  ${chalk.yellow(index + 1)}. ${opt}`);
  });
  console.log();
}

// 显示成功消息
function displaySuccess(message) {
  console.log(chalk.green(`\n${message}\n`));
}

// 显示错误消息
function displayError(message) {
  console.log(chalk.red(`\n❌ ${message}\n`));
}

// 显示信息消息
function displayInfo(message) {
  console.log(chalk.blue(`\nℹ️  ${message}\n`));
}

// 显示警告消息
function displayWarning(message) {
  console.log(chalk.yellow(`\n⚠️  ${message}\n`));
}

module.exports = {
  displayMenu,
  displaySuccess,
  displayError,
  displayInfo,
  displayWarning
};
