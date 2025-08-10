const fs = require('fs-extra')
const path = require('path')
const os = require('os')
const { execute, TEMPLATES } = require('../../src/commands/init')

describe('Init Command', () => {
  let tempDir
  
  beforeEach(async () => {
    // Create temporary directory for tests
    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'cli-test-'))
  })
  
  afterEach(async () => {
    // Clean up temporary directory
    await fs.remove(tempDir)
  })
  
  test('should validate project name', async () => {
    const invalidNames = ['', 'invalid name', 'invalid-name!', '123invalid']
    
    for (const name of invalidNames) {
      await expect(execute(name, { directory: tempDir }))
        .rejects.toThrow('Invalid project name')
    }
  })
  
  test('should create basic project structure', async () => {
    const projectName = 'test-project'
    const projectPath = path.join(tempDir, projectName)
    
    await execute(projectName, {
      template: 'basic',
      directory: tempDir
    })
    
    expect(await fs.pathExists(projectPath)).toBe(true)
    expect(await fs.pathExists(path.join(projectPath, 'README.md'))).toBe(true)
    expect(await fs.pathExists(path.join(projectPath, 'package.json'))).toBe(true)
  })
  
  test('should handle existing directory', async () => {
    const projectName = 'existing-project'
    const projectPath = path.join(tempDir, projectName)
    
    // Create existing directory
    await fs.ensureDir(projectPath)
    await fs.writeFile(path.join(projectPath, 'existing.txt'), 'test')
    
    // Mock inquirer to simulate user choosing not to overwrite
    const mockPrompt = jest.fn().mockResolvedValue({ overwrite: false })
    jest.doMock('inquirer', () => ({ prompt: mockPrompt }))
    
    const { execute: mockedExecute } = require('../../src/commands/init')
    
    await mockedExecute(projectName, {
      template: 'basic',
      directory: tempDir
    })
    
    // Should not have overwritten
    expect(await fs.pathExists(path.join(projectPath, 'existing.txt'))).toBe(true)
    expect(await fs.pathExists(path.join(projectPath, 'README.md'))).toBe(false)
  })
  
  test('should support all available templates', () => {
    const templateKeys = Object.keys(TEMPLATES)
    
    expect(templateKeys).toContain('basic')
    expect(templateKeys).toContain('react')
    expect(templateKeys).toContain('nodejs')
    expect(templateKeys).toContain('python')
    
    // Each template should have required properties
    templateKeys.forEach(key => {
      expect(TEMPLATES[key]).toHaveProperty('name')
      expect(TEMPLATES[key]).toHaveProperty('description')
      expect(TEMPLATES[key]).toHaveProperty('files')
      expect(Array.isArray(TEMPLATES[key].files)).toBe(true)
    })
  })
  
  test('should create template-specific files', async () => {
    const projectName = 'react-project'
    const projectPath = path.join(tempDir, projectName)
    
    await execute(projectName, {
      template: 'react',
      directory: tempDir
    })
    
    const reactTemplate = TEMPLATES.react
    
    for (const file of reactTemplate.files) {
      expect(await fs.pathExists(path.join(projectPath, file))).toBe(true)
    }
  })
  
  test('should handle missing template gracefully', async () => {
    const projectName = 'invalid-template-project'
    
    // Mock inquirer to simulate template selection
    const mockPrompt = jest.fn().mockResolvedValue({ 
      selectedTemplate: 'basic',
      description: 'Test project',
      author: 'Test Author',
      email: 'test@example.com'
    })
    jest.doMock('inquirer', () => ({ prompt: mockPrompt }))
    
    const { execute: mockedExecute } = require('../../src/commands/init')
    
    await expect(mockedExecute(projectName, {
      template: 'nonexistent',
      directory: tempDir
    })).resolves.not.toThrow()
    
    expect(mockPrompt).toHaveBeenCalled()
  })
})
