const fs = require('fs-extra')
const path = require('path')
const chalk = require('chalk')
const inquirer = require('inquirer')
const ora = require('ora')
const { execSync } = require('child_process')

const { logger } = require('../utils/logger')
const { templateEngine } = require('../utils/templateEngine')
const { validateProjectName } = require('../utils/validators')

// Available project templates
const TEMPLATES = {
  basic: {
    name: 'Basic Project',
    description: 'Simple project structure with README',
    files: ['README.md', 'package.json', '.gitignore']
  },
  react: {
    name: 'React Application',
    description: 'React app with Vite and modern tooling',
    files: ['package.json', 'index.html', 'src/App.jsx', 'src/main.jsx']
  },
  nodejs: {
    name: 'Node.js Application',
    description: 'Node.js app with Express and testing setup',
    files: ['package.json', 'index.js', 'src/server.js', 'tests/app.test.js']
  },
  python: {
    name: 'Python Project',
    description: 'Python project with virtual environment setup',
    files: ['requirements.txt', 'main.py', 'src/__init__.py', 'tests/test_main.py']
  }
}

async function execute(projectName, options) {
  // TODO: Validate project name
  if (!validateProjectName(projectName)) {
    throw new Error('Invalid project name. Use only letters, numbers, hyphens, and underscores.')
  }
  
  const targetDir = options.directory || path.join(process.cwd(), projectName)
  
  // TODO: Check if directory already exists
  if (await fs.pathExists(targetDir)) {
    const { overwrite } = await inquirer.prompt([
      {
        type: 'confirm',
        name: 'overwrite',
        message: `Directory ${projectName} already exists. Overwrite?`,
        default: false
      }
    ])
    
    if (!overwrite) {
      logger.info('Operation cancelled.')
      return
    }
    
    await fs.remove(targetDir)
  }
  
  // TODO: Select template if not specified
  let template = options.template
  if (!TEMPLATES[template]) {
    const { selectedTemplate } = await inquirer.prompt([
      {
        type: 'list',
        name: 'selectedTemplate',
        message: 'Select a project template:',
        choices: Object.keys(TEMPLATES).map(key => ({
          name: `${TEMPLATES[key].name} - ${TEMPLATES[key].description}`,
          value: key
        }))
      }
    ])
    template = selectedTemplate
  }
  
  // TODO: Gather additional project information
  const projectInfo = await gatherProjectInfo(projectName, template)
  
  // TODO: Create project structure
  const spinner = ora('Creating project structure...').start()
  
  try {
    await createProjectStructure(targetDir, template, projectInfo)
    spinner.succeed('Project structure created successfully!')
    
    // TODO: Initialize Git repository
    if (options.git) {
      spinner.start('Initializing Git repository...')
      try {
        execSync('git init', { cwd: targetDir, stdio: 'ignore' })
        execSync('git add .', { cwd: targetDir, stdio: 'ignore' })
        execSync('git commit -m "Initial commit"', { cwd: targetDir, stdio: 'ignore' })
        spinner.succeed('Git repository initialized!')
      } catch (error) {
        spinner.warn('Failed to initialize Git repository')
        logger.debug('Git init error:', error.message)
      }
    }
    
    // TODO: Install dependencies
    if (options.install && hasPackageJson(template)) {
      spinner.start('Installing dependencies...')
      try {
        execSync('npm install', { cwd: targetDir, stdio: 'ignore' })
        spinner.succeed('Dependencies installed successfully!')
      } catch (error) {
        spinner.warn('Failed to install dependencies')
        logger.debug('npm install error:', error.message)
      }
    }
    
    // TODO: Display next steps
    displayNextSteps(projectName, targetDir, template, options)
    
  } catch (error) {
    spinner.fail('Failed to create project')
    throw error
  }
}

async function gatherProjectInfo(projectName, template) {
  // TODO: Collect additional information based on template
  const questions = [
    {
      type: 'input',
      name: 'description',
      message: 'Project description:',
      default: `A new ${TEMPLATES[template].name.toLowerCase()}`
    },
    {
      type: 'input',
      name: 'author',
      message: 'Author name:',
      default: process.env.USER || process.env.USERNAME || 'Unknown'
    },
    {
      type: 'input',
      name: 'email',
      message: 'Author email:',
      validate: (input) => {
        if (!input) return true // Optional
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
        return emailRegex.test(input) || 'Please enter a valid email address'
      }
    }
  ]
  
  // TODO: Add template-specific questions
  if (template === 'react') {
    questions.push({
      type: 'confirm',
      name: 'typescript',
      message: 'Use TypeScript?',
      default: false
    })
  }
  
  if (template === 'nodejs') {
    questions.push({
      type: 'list',
      name: 'framework',
      message: 'Choose a framework:',
      choices: ['express', 'fastify', 'koa'],
      default: 'express'
    })
  }
  
  const answers = await inquirer.prompt(questions)
  
  return {
    name: projectName,
    ...answers
  }
}

async function createProjectStructure(targetDir, template, projectInfo) {
  // TODO: Create target directory
  await fs.ensureDir(targetDir)
  
  // TODO: Copy template files
  const templateDir = path.join(__dirname, '../../templates', template)
  
  if (await fs.pathExists(templateDir)) {
    // Copy from template directory
    await fs.copy(templateDir, targetDir)
  } else {
    // Generate basic structure
    await generateBasicStructure(targetDir, template)
  }
  
  // TODO: Process template variables
  await templateEngine.processDirectory(targetDir, projectInfo)
  
  logger.debug(`Project created at: ${targetDir}`)
}

async function generateBasicStructure(targetDir, template) {
  // TODO: Generate basic project structure when templates don't exist
  const templateConfig = TEMPLATES[template]
  
  for (const file of templateConfig.files) {
    const filePath = path.join(targetDir, file)
    await fs.ensureDir(path.dirname(filePath))
    
    // TODO: Generate file content based on type
    let content = ''
    
    if (file === 'README.md') {
      content = generateReadme(template)
    } else if (file === 'package.json') {
      content = generatePackageJson(template)
    } else if (file === '.gitignore') {
      content = generateGitignore(template)
    } else if (file.endsWith('.js') || file.endsWith('.jsx')) {
      content = generateJavaScriptFile(file, template)
    } else if (file.endsWith('.py')) {
      content = generatePythonFile(file, template)
    }
    
    await fs.writeFile(filePath, content)
  }
}

function generateReadme(template) {
  // TODO: Generate README content
  throw new Error('generateReadme not implemented')
}

function generatePackageJson(template) {
  // TODO: Generate package.json content
  throw new Error('generatePackageJson not implemented')
}

function generateGitignore(template) {
  // TODO: Generate .gitignore content
  throw new Error('generateGitignore not implemented')
}

function generateJavaScriptFile(filename, template) {
  // TODO: Generate JavaScript file content
  throw new Error('generateJavaScriptFile not implemented')
}

function generatePythonFile(filename, template) {
  // TODO: Generate Python file content
  throw new Error('generatePythonFile not implemented')
}

function hasPackageJson(template) {
  return ['react', 'nodejs'].includes(template)
}

function displayNextSteps(projectName, targetDir, template, options) {
  console.log('\n' + chalk.green('✨ Project created successfully!'))
  console.log('\nNext steps:')
  console.log(chalk.cyan(`  cd ${projectName}`))
  
  if (!options.install && hasPackageJson(template)) {
    console.log(chalk.cyan('  npm install'))
  }
  
  if (template === 'react') {
    console.log(chalk.cyan('  npm run dev'))
  } else if (template === 'nodejs') {
    console.log(chalk.cyan('  npm start'))
  } else if (template === 'python') {
    console.log(chalk.cyan('  python -m venv venv'))
    console.log(chalk.cyan('  source venv/bin/activate  # On Windows: venv\\Scripts\\activate'))
    console.log(chalk.cyan('  pip install -r requirements.txt'))
  }
  
  console.log('\nHappy coding! 🚀')
}

module.exports = { execute, TEMPLATES }
