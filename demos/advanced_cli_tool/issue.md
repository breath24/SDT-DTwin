# Build Advanced CLI Tool

Create a comprehensive Node.js command-line application in `index.js` with the following capabilities:

## Core CLI Features
1. **Command Structure**:
   - `cli init <project-name>` - Initialize new project with templates
   - `cli generate <type> <name>` - Generate files from templates
   - `cli analyze <directory>` - Analyze project structure and dependencies
   - `cli deploy <environment>` - Deploy project with configuration
   - `cli config <key> [value]` - Manage configuration settings

## Argument Parsing & Validation
1. **Advanced Parsing**:
   - Support for subcommands with nested options
   - Boolean flags, string options, and variadic arguments
   - Required vs optional parameters with validation
   - Help text generation for all commands

2. **Input Validation**:
   - File/directory existence checks
   - Format validation (emails, URLs, etc.)
   - Custom validation rules
   - Interactive prompts for missing required inputs

## File System Operations
1. **Template System**:
   - Multiple project templates (React, Node.js, Python)
   - Variable substitution in template files
   - Directory structure generation
   - Binary file handling

2. **File Management**:
   - Recursive directory operations
   - File watching and change detection
   - Backup and restore functionality
   - Compression and archiving

## Interactive Features
1. **User Prompts**:
   - Multi-select menus with search
   - Password/hidden input handling
   - Progress bars for long operations
   - Confirmation dialogs

2. **Terminal Enhancements**:
   - Colored output with themes
   - Formatted tables and lists
   - Spinners and loading indicators
   - Box drawing and layouts

## Configuration Management
1. **Settings System**:
   - Global and project-specific configs
   - JSON/YAML configuration files
   - Environment variable integration
   - Configuration validation schemas

2. **Profile Management**:
   - Multiple deployment profiles
   - Credential management
   - Default value cascading

## Advanced Features
1. **Plugin System**:
   - Dynamic plugin loading
   - Hook system for extensibility
   - Plugin dependency management
   - Built-in plugin registry

2. **Performance**:
   - Parallel processing for file operations
   - Caching for expensive operations
   - Memory-efficient streaming
   - Process management

## Error Handling & Logging
1. **Robust Error Handling**:
   - Graceful error recovery
   - User-friendly error messages
   - Debug mode with stack traces
   - Error reporting and telemetry

2. **Logging System**:
   - Multiple log levels
   - File and console output
   - Log rotation and cleanup
   - Structured logging format

Include comprehensive testing, documentation, and cross-platform compatibility. Make all tests pass with `npm test`.
