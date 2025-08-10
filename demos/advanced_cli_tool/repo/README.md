# Advanced CLI Tool

A comprehensive command-line interface tool for project management, code generation, and automation workflows.

## Features

### 🚀 Project Initialization
- Multiple project templates (React, Node.js, Python, Basic)
- Interactive project setup with customizable options
- Automatic Git repository initialization
- Dependency installation and configuration

### 🔧 Code Generation
- File and component generation from templates
- Template variable substitution
- Custom template support
- Dry-run mode for preview

### 📊 Project Analysis
- Project structure analysis
- Dependency scanning and reporting
- Code quality metrics
- Customizable output formats (JSON, table, summary)

### 🚢 Deployment Management
- Multi-environment deployment configurations
- Profile-based deployment settings
- Build and test integration
- Deployment preview and rollback

### ⚙️ Configuration Management
- Global and project-specific configurations
- YAML-based configuration files
- Environment variable integration
- Configuration validation and defaults

## Installation

### Global Installation
```bash
npm install -g advanced-cli-tool
```

### Development Setup
```bash
git clone <repository-url>
cd advanced-cli-tool
npm install
npm link
```

## Usage

### Initialize a New Project
```bash
# Interactive template selection
cli init my-project

# Specify template directly
cli init my-react-app --template react --git --install

# Custom directory
cli init my-app --directory /path/to/projects --template nodejs
```

### Generate Code
```bash
# Generate component
cli generate component MyComponent

# Generate with custom template
cli generate page AboutPage --template custom-page

# Preview generation (dry-run)
cli generate service UserService --dry-run
```

### Analyze Project
```bash
# Analyze current directory
cli analyze

# Analyze specific directory with detailed output
cli analyze /path/to/project --recursive --output json --dependencies

# Save analysis to file
cli analyze --save analysis-report.json
```

### Deploy Application
```bash
# Deploy to staging environment
cli deploy staging

# Deploy with custom configuration
cli deploy production --config deploy.yaml --skip-tests

# Preview deployment plan
cli deploy staging --dry-run
```

### Manage Configuration
```bash
# List all configuration values
cli config --list

# Set global configuration
cli config theme dark --global

# Set project-specific setting
cli config deployment.defaultEnvironment staging

# Edit configuration in default editor
cli config --edit
```

## Configuration

### Global Configuration
Located at `~/.cli-tool/config.yaml`

```yaml
theme: auto
editor: code
templates:
  directory: ~/.cli-tool/templates
  cache: true
deployment:
  defaultEnvironment: development
  profiles:
    staging:
      host: staging.example.com
      port: 22
      username: deploy
    production:
      host: prod.example.com
      port: 22
      username: deploy
preferences:
  confirmDestructive: true
  verboseOutput: false
  autoUpdate: true
```

### Project Configuration
Located at `.cli-tool.yaml` in project root

```yaml
deployment:
  defaultEnvironment: staging
  buildCommand: npm run build
  testCommand: npm test
  outputDirectory: dist
templates:
  components: ./templates/components
  pages: ./templates/pages
```

## Templates

### Built-in Templates

#### Basic Project
- Simple project structure
- README.md and basic configuration
- Git repository setup

#### React Application
- Modern React setup with Vite
- TypeScript support option
- ESLint and Prettier configuration
- Testing setup with Jest

#### Node.js Application
- Express.js server setup
- Framework selection (Express, Fastify, Koa)
- Testing configuration
- Docker support

#### Python Project
- Virtual environment setup
- Requirements.txt with common packages
- Testing with pytest
- Basic project structure

### Custom Templates

Create custom templates in your templates directory:

```
~/.cli-tool/templates/
├── my-template/
│   ├── template.yaml
│   ├── {{name}}.js
│   ├── package.json
│   └── README.md
```

Template variables:
- `{{name}}` - Project/component name
- `{{description}}` - Project description
- `{{author}}` - Author name
- `{{email}}` - Author email
- Custom variables from prompts

## Plugin System

### Installing Plugins
```bash
cli plugin install my-custom-plugin
cli plugin list
cli plugin enable my-custom-plugin
```

### Creating Plugins
```javascript
// plugin.js
module.exports = {
  name: 'my-plugin',
  version: '1.0.0',
  commands: {
    'my-command': require('./commands/my-command')
  },
  hooks: {
    'before:deploy': async (context) => {
      // Custom pre-deployment logic
    }
  }
}
```

## Advanced Features

### Environment Variables
- `CLI_CONFIG_PATH` - Custom configuration file path
- `CLI_TEMPLATE_DIR` - Custom templates directory
- `CLI_LOG_LEVEL` - Logging verbosity (error, warn, info, debug)
- `NO_COLOR` - Disable colored output

### Scripting and Automation
```bash
# Use in scripts
cli init project-$DATE --template react --no-git --install
cli analyze --output json | jq '.dependencies.outdated'
cli deploy production --config prod.yaml && cli notify slack
```

### Performance Options
- Template caching for faster generation
- Parallel file operations
- Incremental builds and deployments
- Memory-efficient large file handling

## Testing

```bash
# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Watch mode for development
npm run test:watch

# Integration tests
npm run test:integration
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

### Development Commands
```bash
# Install dependencies
npm install

# Link for local development
npm link

# Run linting
npm run lint

# Fix linting issues
npm run lint:fix

# Build documentation
npm run docs:build
```

## Troubleshooting

### Common Issues

#### Permission Errors
```bash
# Fix npm permissions
sudo chown -R $(whoami) ~/.npm
sudo chown -R $(whoami) /usr/local/lib/node_modules
```

#### Template Not Found
```bash
# Verify template directory
cli config templates.directory
ls ~/.cli-tool/templates/

# Reset to defaults
cli config templates --delete
```

#### Configuration Issues
```bash
# Validate configuration
cli config --validate

# Reset to defaults
cli config --reset

# Check global vs local config
cli config --list --global
cli config --list
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- GitHub Issues: [Report bugs and request features](https://github.com/user/advanced-cli-tool/issues)
- Documentation: [Full documentation](https://docs.cli-tool.com)
- Community: [Discord server](https://discord.gg/cli-tool)
