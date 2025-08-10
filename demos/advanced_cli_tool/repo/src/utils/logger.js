const chalk = require('chalk')
const fs = require('fs-extra')
const path = require('path')

// Log levels
const LOG_LEVELS = {
  ERROR: 0,
  WARN: 1,
  INFO: 2,
  DEBUG: 3
}

class Logger {
  constructor() {
    this.level = LOG_LEVELS.INFO
    this.logFile = null
    this.enableColors = true
  }
  
  // TODO: Set log level
  setLevel(level) {
    if (typeof level === 'string') {
      this.level = LOG_LEVELS[level.toUpperCase()] ?? LOG_LEVELS.INFO
    } else {
      this.level = level
    }
  }
  
  // TODO: Set log file for persistent logging
  setLogFile(filePath) {
    this.logFile = filePath
    // Ensure log directory exists
    fs.ensureDirSync(path.dirname(filePath))
  }
  
  // TODO: Enable/disable colored output
  setColors(enabled) {
    this.enableColors = enabled
  }
  
  // TODO: Log error messages
  error(...args) {
    if (this.level >= LOG_LEVELS.ERROR) {
      this._log('ERROR', chalk.red, ...args)
    }
  }
  
  // TODO: Log warning messages
  warn(...args) {
    if (this.level >= LOG_LEVELS.WARN) {
      this._log('WARN', chalk.yellow, ...args)
    }
  }
  
  // TODO: Log info messages
  info(...args) {
    if (this.level >= LOG_LEVELS.INFO) {
      this._log('INFO', chalk.blue, ...args)
    }
  }
  
  // TODO: Log debug messages
  debug(...args) {
    if (this.level >= LOG_LEVELS.DEBUG) {
      this._log('DEBUG', chalk.gray, ...args)
    }
  }
  
  // TODO: Log success messages
  success(...args) {
    if (this.level >= LOG_LEVELS.INFO) {
      this._log('SUCCESS', chalk.green, ...args)
    }
  }
  
  // TODO: Internal logging method
  _log(level, colorFn, ...args) {
    const timestamp = new Date().toISOString()
    const prefix = `[${timestamp}] [${level}]`
    
    // Format message
    const message = args.map(arg => 
      typeof arg === 'object' ? JSON.stringify(arg, null, 2) : String(arg)
    ).join(' ')
    
    // Console output with colors
    if (this.enableColors) {
      console.log(colorFn(`${prefix} ${message}`))
    } else {
      console.log(`${prefix} ${message}`)
    }
    
    // File output (always without colors)
    if (this.logFile) {
      try {
        fs.appendFileSync(this.logFile, `${prefix} ${message}\n`)
      } catch (error) {
        console.error('Failed to write to log file:', error.message)
      }
    }
  }
  
  // TODO: Create child logger with prefix
  child(prefix) {
    const childLogger = new Logger()
    childLogger.level = this.level
    childLogger.logFile = this.logFile
    childLogger.enableColors = this.enableColors
    childLogger._prefix = prefix
    
    // Override _log to include prefix
    const originalLog = childLogger._log.bind(childLogger)
    childLogger._log = (level, colorFn, ...args) => {
      originalLog(level, colorFn, `[${prefix}]`, ...args)
    }
    
    return childLogger
  }
}

// Create default logger instance
const logger = new Logger()

// TODO: Configure logger based on environment
if (process.env.NODE_ENV === 'development') {
  logger.setLevel('DEBUG')
} else if (process.env.NODE_ENV === 'test') {
  logger.setLevel('ERROR')
}

// TODO: Disable colors if NO_COLOR environment variable is set
if (process.env.NO_COLOR) {
  logger.setColors(false)
}

module.exports = { Logger, logger, LOG_LEVELS }
