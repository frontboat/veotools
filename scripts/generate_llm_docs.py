#!/usr/bin/env python3
"""Generate LLM-friendly documentation from Python source code.

This script extracts docstrings and function signatures from all Python files
in the project and creates a comprehensive markdown or XML document suitable
for LLM consumption.
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


class DocExtractor(ast.NodeVisitor):
    """Extract docstrings and signatures from Python AST."""
    
    def __init__(self):
        self.items = []
        self.current_class = None
    
    def visit_ClassDef(self, node):
        """Extract class documentation."""
        class_info = {
            'type': 'class',
            'name': node.name,
            'docstring': ast.get_docstring(node),
            'methods': [],
            'lineno': node.lineno
        }
        
        # Store current class context
        prev_class = self.current_class
        self.current_class = class_info
        
        # Visit methods
        self.generic_visit(node)
        
        # Restore previous context and save
        self.current_class = prev_class
        self.items.append(class_info)
    
    def visit_FunctionDef(self, node):
        """Extract function/method documentation."""
        # Get function signature
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)
        
        signature = f"{node.name}({', '.join(args)})"
        if node.returns:
            signature += f" -> {ast.unparse(node.returns)}"
        
        func_info = {
            'type': 'method' if self.current_class else 'function',
            'name': node.name,
            'signature': signature,
            'docstring': ast.get_docstring(node),
            'lineno': node.lineno
        }
        
        if self.current_class:
            self.current_class['methods'].append(func_info)
        else:
            self.items.append(func_info)
        
        # Don't visit nested functions
        # self.generic_visit(node)


def extract_module_docs(file_path: Path) -> Dict[str, Any]:
    """Extract documentation from a Python module."""
    with open(file_path, 'r') as f:
        source = f.read()
    
    try:
        tree = ast.parse(source)
        module_doc = ast.get_docstring(tree)
        
        extractor = DocExtractor()
        extractor.visit(tree)
        
        return {
            'path': str(file_path),
            'module_docstring': module_doc,
            'items': extractor.items
        }
    except Exception as e:
        return {
            'path': str(file_path),
            'error': str(e)
        }


def generate_markdown(modules: List[Dict[str, Any]], project_info: Dict) -> str:
    """Generate markdown documentation."""
    lines = []
    
    # Header
    lines.append(f"# {project_info['name']} - LLM Documentation")
    lines.append(f"\nGenerated: {datetime.now().isoformat()}")
    lines.append(f"\nVersion: {project_info.get('version', 'unknown')}")
    lines.append(f"\n{project_info.get('description', '')}\n")
    
    # Table of contents
    lines.append("## Table of Contents\n")
    for module in modules:
        if 'error' not in module:
            module_name = Path(module['path']).stem
            lines.append(f"- [{module_name}](#{module_name})")
    lines.append("")
    
    # Module documentation
    for module in modules:
        if 'error' in module:
            continue
            
        module_path = Path(module['path'])
        module_name = module_path.stem
        
        lines.append(f"\n## {module_name}")
        lines.append(f"\n`{module['path']}`\n")
        
        if module['module_docstring']:
            lines.append(f"{module['module_docstring']}\n")
        
        # Classes
        classes = [item for item in module['items'] if item['type'] == 'class']
        if classes:
            lines.append("### Classes\n")
            for cls in classes:
                lines.append(f"#### {cls['name']}")
                if cls['docstring']:
                    lines.append(f"\n{cls['docstring']}\n")
                
                if cls['methods']:
                    lines.append("\n**Methods:**\n")
                    for method in cls['methods']:
                        lines.append(f"- `{method['signature']}`")
                        if method['docstring']:
                            # First line of docstring
                            first_line = method['docstring'].split('\n')[0]
                            lines.append(f"  - {first_line}")
                lines.append("")
        
        # Functions
        functions = [item for item in module['items'] if item['type'] == 'function']
        if functions:
            lines.append("### Functions\n")
            for func in functions:
                lines.append(f"#### `{func['signature']}`")
                if func['docstring']:
                    lines.append(f"\n{func['docstring']}\n")
                else:
                    lines.append("")
    
    return '\n'.join(lines)


def generate_xml(modules: List[Dict[str, Any]], project_info: Dict) -> str:
    """Generate XML documentation."""
    lines = []
    
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(f'<project name="{project_info["name"]}" version="{project_info.get("version", "")}">')
    lines.append(f'  <description>{project_info.get("description", "")}</description>')
    lines.append(f'  <generated>{datetime.now().isoformat()}</generated>')
    lines.append('  <modules>')
    
    for module in modules:
        if 'error' in module:
            continue
            
        lines.append(f'    <module path="{module["path"]}">')
        
        if module['module_docstring']:
            lines.append(f'      <docstring><![CDATA[{module["module_docstring"]}]]></docstring>')
        
        # Classes
        classes = [item for item in module['items'] if item['type'] == 'class']
        for cls in classes:
            lines.append(f'      <class name="{cls["name"]}" line="{cls["lineno"]}">')
            if cls['docstring']:
                lines.append(f'        <docstring><![CDATA[{cls["docstring"]}]]></docstring>')
            
            if cls['methods']:
                lines.append('        <methods>')
                for method in cls['methods']:
                    lines.append(f'          <method name="{method["name"]}" signature="{method["signature"]}">')
                    if method['docstring']:
                        lines.append(f'            <docstring><![CDATA[{method["docstring"]}]]></docstring>')
                    lines.append('          </method>')
                lines.append('        </methods>')
            lines.append('      </class>')
        
        # Functions
        functions = [item for item in module['items'] if item['type'] == 'function']
        for func in functions:
            lines.append(f'      <function name="{func["name"]}" signature="{func["signature"]}" line="{func["lineno"]}">')
            if func['docstring']:
                lines.append(f'        <docstring><![CDATA[{func["docstring"]}]]></docstring>')
            lines.append('      </function>')
        
        lines.append('    </module>')
    
    lines.append('  </modules>')
    lines.append('</project>')
    
    return '\n'.join(lines)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate LLM-friendly documentation')
    parser.add_argument('--format', choices=['md', 'xml', 'json'], default='md',
                        help='Output format (default: md)')
    parser.add_argument('--output', '-o', default='llm.txt',
                        help='Output file (default: llm.txt)')
    parser.add_argument('--src', default='src/veotools',
                        help='Source directory (default: src/veotools)')
    args = parser.parse_args()
    
    # Get project info
    project_info = {
        'name': 'Veotools',
        'description': 'Python SDK and MCP server for video generation with Google Veo',
        'version': '0.1.8'
    }
    
    # Try to get version from pyproject.toml
    pyproject_path = Path('pyproject.toml')
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
                project_info['description'] = data.get('project', {}).get('description', project_info['description'])
    
    # Find all Python files
    src_path = Path(args.src)
    if not src_path.exists():
        print(f"Error: Source directory '{src_path}' not found")
        sys.exit(1)
    
    python_files = sorted(src_path.glob('**/*.py'))
    
    # Extract documentation from each file
    modules = []
    for file_path in python_files:
        if '__pycache__' in str(file_path):
            continue
        print(f"Processing {file_path}...")
        module_docs = extract_module_docs(file_path)
        modules.append(module_docs)
    
    # Generate output
    if args.format == 'md':
        output = generate_markdown(modules, project_info)
    elif args.format == 'xml':
        output = generate_xml(modules, project_info)
    else:  # json
        output = json.dumps({
            'project': project_info,
            'modules': modules
        }, indent=2)
    
    # Write output
    output_path = Path(args.output)
    with open(output_path, 'w') as f:
        f.write(output)
    
    print(f"\n✅ Generated {args.format.upper()} documentation: {output_path}")
    print(f"   Processed {len(modules)} modules")
    print(f"   Output size: {len(output):,} characters")


if __name__ == '__main__':
    main()