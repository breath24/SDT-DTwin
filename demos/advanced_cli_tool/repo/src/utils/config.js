const fs = require('fs-extra')
const path = require('path')
const os = require('os')
const yaml = require('yaml')
const Joi = require('joi')

// Configuration file paths
const CONFIG_DIR = path.join(os.homedir(), '.cli-tool')
const GLOBAL_CONFIG_FILE = path.join(CONFIG_DIR, 'config.yaml')
const LOCAL_CONFIG_FILE = path.join(process.cwd(), '.cli-tool.yaml')

// Configuration schema for validation
const configSchema = Joi.object({
  // General settings
  theme: Joi.string().valid('light', 'dark', 'auto').default('auto'),
  editor: Joi.string().default(process.env.EDITOR || 'nano'),
  
  // Template settings
  templates: Joi.object({
    directory: Joi.string(),
    registry: Joi.string().uri(),
    cache: Joi.boolean().default(true)
  }).default({}),
  
  // Deployment settings
  deployment: Joi.object({
    defaultEnvironment: Joi.string().default('development'),
    profiles: Joi.object().pattern(
      Joi.string(), 
      Joi.object({
        host: Joi.string(),
        port: Joi.number(),
        username: Joi.string(),
        keyFile: Joi.string()
      })
    )
  }).default({}),
  
  // Plugin settings
  plugins: Joi.object({
    enabled: Joi.array().items(Joi.string()).default([]),
    registry: Joi.string().uri()
  }).default({}),
  
  // User preferences
  preferences: Joi.object({
    confirmDestructive: Joi.boolean().default(true),
    verboseOutput: Joi.boolean().default(false),
    autoUpdate: Joi.boolean().default(true)
  }).default({})
}).default({})

class ConfigManager {
  constructor() {
    this.globalConfig = {}
    this.localConfig = {}
    this.mergedConfig = {}
  }
  
  // TODO: Load configuration from files
  async load(customConfigPath = null) {
    try {
      // Load global configuration
      if (await fs.pathExists(GLOBAL_CONFIG_FILE)) {
        const globalContent = await fs.readFile(GLOBAL_CONFIG_FILE, 'utf8')
        this.globalConfig = yaml.parse(globalContent) || {}
      }
      
      // Load local configuration
      const localPath = customConfigPath || LOCAL_CONFIG_FILE
      if (await fs.pathExists(localPath)) {
        const localContent = await fs.readFile(localPath, 'utf8')
        this.localConfig = yaml.parse(localContent) || {}
      }
      
      // Merge configurations (local overrides global)
      this.mergedConfig = this._mergeConfigs(this.globalConfig, this.localConfig)
      
      // Validate merged configuration
      const { error, value } = configSchema.validate(this.mergedConfig)
      if (error) {
        throw new Error(`Configuration validation failed: ${error.message}`)
      }
      
      this.mergedConfig = value
      
    } catch (error) {
      throw new Error(`Failed to load configuration: ${error.message}`)
    }
  }
  
  // TODO: Save configuration to file
  async save(config, isGlobal = false) {
    try {
      const filePath = isGlobal ? GLOBAL_CONFIG_FILE : LOCAL_CONFIG_FILE
      
      // Validate configuration before saving
      const { error, value } = configSchema.validate(config)
      if (error) {
        throw new Error(`Configuration validation failed: ${error.message}`)
      }
      
      // Ensure directory exists
      await fs.ensureDir(path.dirname(filePath))
      
      // Save as YAML
      const yamlContent = yaml.stringify(value)
      await fs.writeFile(filePath, yamlContent, 'utf8')
      
      // Update internal state
      if (isGlobal) {
        this.globalConfig = value
      } else {
        this.localConfig = value
      }
      
      this.mergedConfig = this._mergeConfigs(this.globalConfig, this.localConfig)
      
    } catch (error) {
      throw new Error(`Failed to save configuration: ${error.message}`)
    }
  }
  
  // TODO: Get configuration value by key
  get(key) {
    const keys = key.split('.')
    let value = this.mergedConfig
    
    for (const k of keys) {
      if (value && typeof value === 'object' && k in value) {
        value = value[k]
      } else {
        return undefined
      }
    }
    
    return value
  }
  
  // TODO: Set configuration value by key
  async set(key, value, isGlobal = false) {
    const keys = key.split('.')
    const config = isGlobal ? { ...this.globalConfig } : { ...this.localConfig }
    
    // Navigate to the parent object
    let current = config
    for (let i = 0; i < keys.length - 1; i++) {
      if (!(keys[i] in current) || typeof current[keys[i]] !== 'object') {
        current[keys[i]] = {}
      }
      current = current[keys[i]]
    }
    
    // Set the value
    current[keys[keys.length - 1]] = value
    
    // Save the updated configuration
    await this.save(config, isGlobal)
  }
  
  // TODO: Delete configuration key
  async delete(key, isGlobal = false) {
    const keys = key.split('.')
    const config = isGlobal ? { ...this.globalConfig } : { ...this.localConfig }
    
    // Navigate to the parent object
    let current = config
    for (let i = 0; i < keys.length - 1; i++) {
      if (!(keys[i] in current) || typeof current[keys[i]] !== 'object') {
        return // Key doesn't exist
      }
      current = current[keys[i]]
    }
    
    // Delete the key
    delete current[keys[keys.length - 1]]
    
    // Save the updated configuration
    await this.save(config, isGlobal)
  }
  
  // TODO: List all configuration keys and values
  list() {
    return this._flattenObject(this.mergedConfig)
  }
  
  // TODO: Reset configuration to defaults
  async reset(isGlobal = false) {
    const { value } = configSchema.validate({})
    await this.save(value, isGlobal)
  }
  
  // TODO: Merge two configuration objects
  _mergeConfigs(global, local) {
    return this._deepMerge(global, local)
  }
  
  // TODO: Deep merge utility function
  _deepMerge(obj1, obj2) {
    const result = { ...obj1 }
    
    for (const key in obj2) {
      if (obj2[key] && typeof obj2[key] === 'object' && !Array.isArray(obj2[key])) {
        result[key] = this._deepMerge(result[key] || {}, obj2[key])
      } else {
        result[key] = obj2[key]
      }
    }
    
    return result
  }
  
  // TODO: Flatten nested object for listing
  _flattenObject(obj, prefix = '') {
    const flattened = {}
    
    for (const key in obj) {
      const fullKey = prefix ? `${prefix}.${key}` : key
      
      if (obj[key] && typeof obj[key] === 'object' && !Array.isArray(obj[key])) {
        Object.assign(flattened, this._flattenObject(obj[key], fullKey))
      } else {
        flattened[fullKey] = obj[key]
      }
    }
    
    return flattened
  }
}

// Create singleton instance
const configManager = new ConfigManager()

// Convenience functions
async function loadConfig(customPath) {
  await configManager.load(customPath)
  return configManager.mergedConfig
}

async function ensureConfigDir() {
  await fs.ensureDir(CONFIG_DIR)
}

module.exports = {
  ConfigManager,
  configManager,
  loadConfig,
  ensureConfigDir,
  CONFIG_DIR,
  GLOBAL_CONFIG_FILE,
  LOCAL_CONFIG_FILE
}
