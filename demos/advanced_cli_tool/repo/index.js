#!/usr/bin/env node

const { Command } = require('commander')
const chalk = require('chalk')
const figlet = require('figlet')
const path = require('path')
const fs = require('fs-extra')

// Import command modules
const initCommand = require('./src/commands/init')
const generateCommand = require('./src/commands/generate')
const analyzeCommand = require('./src/commands/analyze')
const deployCommand = require('./src/commands/deploy')
const configCommand = require('./src/commands/config')

// Import utilities
const { loadConfig, ensureConfigDir } = require('./src/utils/config')
const { setupErrorHandling } = require('./src/utils/errorHandler')
const { logger } = require('./src/utils/logger')

const program = new Command()

// TODO: Set up CLI program with global options
async function setupCLI() {
  try {
    // TODO: Display welcome banner
    console.log(chalk.blue(figlet.textSync('CLI Tool', { horizontalLayout: 'full' })))
    
    // TODO: Set up global program configuration
    program
      .name('cli')
      .description('Advanced CLI tool for project management and automation')
      .version('1.0.0')
      .option('-v, --verbose', 'Enable verbose logging')
      .option('-q, --quiet', 'Suppress non-error output')
      .option('--no-color', 'Disable colored output')
      .option('--config <path>', 'Specify config file path')
    
    // TODO: Ensure configuration directory exists
    await ensureConfigDir()
    
    // TODO: Load global configuration
    const config = await loadConfig(program.opts().config)
    
    // TODO: Set up error handling
    setupErrorHandling(program.opts().verbose)
    
    // TODO: Register all commands
    registerCommands()
    
    // TODO: Parse command line arguments
    await program.parseAsync(process.argv)
    
  } catch (error) {
    console.error(chalk.red('Failed to initialize CLI:'), error.message)
    process.exit(1)
  }
}

function registerCommands() {
  // TODO: Register init command
  program
    .command('init <project-name>')
    .description('Initialize a new project with templates')
    .option('-t, --template <type>', 'Project template type', 'basic')
    .option('-d, --directory <path>', 'Target directory')
    .option('--git', 'Initialize Git repository')
    .option('--install', 'Install dependencies automatically')
    .action(async (projectName, options) => {
      try {
        await initCommand.execute(projectName, options)
      } catch (error) {
        logger.error('Init command failed:', error)
        process.exit(1)
      }
    })
  
  // TODO: Register generate command
  program
    .command('generate <type> <name>')
    .alias('g')
    .description('Generate files from templates')
    .option('-t, --template <template>', 'Template to use')
    .option('-p, --path <path>', 'Target path for generated files')
    .option('--dry-run', 'Show what would be generated without creating files')
    .action(async (type, name, options) => {
      try {
        await generateCommand.execute(type, name, options)
      } catch (error) {
        logger.error('Generate command failed:', error)
        process.exit(1)
      }
    })
  
  // TODO: Register analyze command
  program
    .command('analyze [directory]')
    .description('Analyze project structure and dependencies')
    .option('-r, --recursive', 'Analyze subdirectories recursively')
    .option('-o, --output <format>', 'Output format (json, table, summary)', 'summary')
    .option('--save <file>', 'Save analysis to file')
    .option('--dependencies', 'Include dependency analysis')
    .action(async (directory, options) => {
      try {
        await analyzeCommand.execute(directory || process.cwd(), options)
      } catch (error) {
        logger.error('Analyze command failed:', error)
        process.exit(1)
      }
    })
  
  // TODO: Register deploy command
  program
    .command('deploy <environment>')
    .description('Deploy project with configuration')
    .option('-c, --config <file>', 'Deployment configuration file')
    .option('--dry-run', 'Show deployment plan without executing')
    .option('--skip-build', 'Skip build step')
    .option('--skip-tests', 'Skip test execution')
    .action(async (environment, options) => {
      try {
        await deployCommand.execute(environment, options)
      } catch (error) {
        logger.error('Deploy command failed:', error)
        process.exit(1)
      }
    })
  
  // TODO: Register config command
  program
    .command('config <key> [value]')
    .description('Manage configuration settings')
    .option('-g, --global', 'Use global configuration')
    .option('-l, --list', 'List all configuration values')
    .option('-d, --delete', 'Delete configuration key')
    .option('-e, --edit', 'Open configuration in editor')
    .action(async (key, value, options) => {
      try {
        await configCommand.execute(key, value, options)
      } catch (error) {
        logger.error('Config command failed:', error)
        process.exit(1)
      }
    })
  
  // TODO: Add help command with examples
  program
    .command('help [command]')
    .description('Display help for commands')
    .action((command) => {
      if (command) {
        program.commands.find(cmd => cmd.name() === command)?.help()
      } else {
        program.help()
      }
    })
}

// TODO: Handle unhandled rejections and exceptions
process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled Rejection at:', promise, 'reason:', reason)
  process.exit(1)
})

process.on('uncaughtException', (error) => {
  logger.error('Uncaught Exception:', error)
  process.exit(1)
})

// TODO: Handle process signals gracefully
process.on('SIGINT', () => {
  console.log(chalk.yellow('\nReceived SIGINT. Gracefully shutting down...'))
  process.exit(0)
})

process.on('SIGTERM', () => {
  console.log(chalk.yellow('\nReceived SIGTERM. Gracefully shutting down...'))
  process.exit(0)
})

// Start the CLI application
if (require.main === module) {
  setupCLI().catch((error) => {
    console.error(chalk.red('Fatal error:'), error.message)
    process.exit(1)
  })
}

module.exports = { program, setupCLI }
