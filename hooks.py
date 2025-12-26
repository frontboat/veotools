"""MkDocs hooks for auto-generating LLM documentation.

This module provides hooks that run during the MkDocs build process
to automatically generate llm.txt and make it available as part of
the documentation site.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path so we can import our script
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.generate_llm_docs import extract_module_docs, generate_markdown, generate_xml


def on_pre_build(config):
    """Hook that runs before the documentation is built.
    
    This generates the llm.txt file and places it in the docs directory
    so it will be included in the built site.
    """
    print("🤖 Generating LLM documentation...")
    
    # Get project info from mkdocs config
    project_info = {
        'name': config.get('site_name', 'Veotools'),
        'description': config.get('site_description', 'Python SDK for video generation'),
        'version': '0.1.8'
    }
    
    # Try to get version from pyproject.toml
    pyproject_path = project_root / 'pyproject.toml'
    if pyproject_path.exists():
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                tomllib = None
        
        if tomllib:
            with open(pyproject_path, 'rb') as f:
                data = tomllib.load(f)
                project_info['version'] = data.get('project', {}).get('version', '0.1.8')
    
    # Find all Python files in src/veotools
    src_path = project_root / 'src' / 'veotools'
    python_files = sorted(src_path.glob('**/*.py'))
    
    # Extract documentation
    modules = []
    for file_path in python_files:
        if '__pycache__' in str(file_path):
            continue
        module_docs = extract_module_docs(file_path)
        modules.append(module_docs)
    
    # Generate both markdown and XML versions
    markdown_output = generate_markdown(modules, project_info)
    xml_output = generate_xml(modules, project_info)
    
    # Save to docs directory (will be copied to site)
    docs_dir = Path(config['docs_dir'])
    
    # Save markdown version as llm.txt
    llm_txt_path = docs_dir / 'llm.txt'
    with open(llm_txt_path, 'w') as f:
        f.write(markdown_output)
    print(f"   ✅ Generated llm.txt ({len(markdown_output):,} chars)")
    
    # Save XML version
    llm_xml_path = docs_dir / 'llm.xml'
    with open(llm_xml_path, 'w') as f:
        f.write(xml_output)
    print(f"   ✅ Generated llm.xml ({len(xml_output):,} chars)")
    
    # Also create an llm.md page that will be rendered as HTML
    llm_md_content = f"""# LLM Documentation

This page provides machine-readable documentation for Large Language Models (LLMs) to understand the Veotools codebase.

## Available Formats

- **[Markdown/Text Format](../llm.txt)** - Plain text markdown format (llm.txt standard)
- **[XML Format](../llm.xml)** - Structured XML format for parsing

## About

These files are automatically generated from the source code docstrings during the documentation build process. They contain:

- Complete API documentation
- All function and class signatures  
- Comprehensive docstrings
- Module structure and organization

## Usage

### For LLM Providers

Add the following to your LLM's context:

```
https://your-docs-site.com/llm.txt
```

### For Developers

When asking an LLM about this codebase, you can reference:

```
Please read the documentation at https://your-docs-site.com/llm.txt to understand the Veotools API
```

## Auto-Generation

These files are regenerated automatically whenever the documentation is built, ensuring they always reflect the current state of the codebase.

---

*Last generated: {datetime.now().isoformat()}*
"""
    
    llm_md_path = docs_dir / 'llm.md'
    with open(llm_md_path, 'w') as f:
        f.write(llm_md_content)
    print(f"   ✅ Created llm.md documentation page")
    
    return config


def on_post_build(config):
    """Hook that runs after the site is built.
    
    This ensures the llm.txt and llm.xml files are in the root of the site.
    """
    site_dir = Path(config['site_dir'])
    docs_dir = Path(config['docs_dir'])
    
    # Copy llm files to site root for easy access
    for filename in ['llm.txt', 'llm.xml']:
        src = docs_dir / filename
        dst = site_dir / filename
        if src.exists():
            import shutil
            shutil.copy2(src, dst)
            print(f"   ✅ Copied {filename} to site root")
    
    return config