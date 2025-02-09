#!/usr/bin/env python3

import os
import re
import glob
from pathlib import Path

class SConsToCMakeConverter:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        
    def convert(self):
        """Convert SCons build system to CMake."""
        print("Converting SCons to CMake...")
        
        # Parse SCons files
        scons_options = self._parse_sconstruct()
        platform_configs = self._parse_platform_configs()
        modules = self._parse_modules()
        
        # Generate CMake files
        self._generate_root_cmakelists(scons_options)
        self._generate_platform_cmake_files(platform_configs)
        self._generate_core_cmake_files()
        self._generate_module_cmake_files(modules)
        
    def _parse_sconstruct(self):
        """Parse SConstruct file for build options."""
        options = {}
        sconstruct = self.root_dir / "SConstruct"
        
        with open(sconstruct) as f:
            content = f.read()
            
        # Extract build options
        for line in content.split('\n'):
            if line.strip().startswith('opts.Add('):
                option = self._parse_option(line)
                if option:
                    options[option['name']] = option
                    
        return options
        
    def _parse_option(self, line):
        """Parse a single SCons option line."""
        # Example: opts.Add(BoolVariable("builtin_freetype", "Use builtin FreeType library", True))
        match = re.search(r'opts\.Add\((.*?)\)', line)
        if not match:
            return None
            
        args = match.group(1)
        
        # Parse BoolVariable
        bool_match = re.search(r'BoolVariable\("([^"]+)",\s*"([^"]+)",\s*(\w+)\)', args)
        if bool_match:
            return {
                'type': 'bool',
                'name': bool_match.group(1),
                'desc': bool_match.group(2),
                'default': bool_match.group(3).lower() == 'true'
            }
            
        # Parse EnumVariable
        enum_match = re.search(r'EnumVariable\("([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*\((.*?)\)\)', args)
        if enum_match:
            return {
                'type': 'enum',
                'name': enum_match.group(1),
                'desc': enum_match.group(2),
                'default': enum_match.group(3),
                'values': [v.strip(' "\'') for v in enum_match.group(4).split(',')]
            }
            
        # Parse StringVariable
        str_match = re.search(r'"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"', args)
        if str_match:
            return {
                'type': 'string',
                'name': str_match.group(1),
                'desc': str_match.group(2),
                'default': str_match.group(3)
            }
            
        return None
        
    def _parse_platform_configs(self):
        """Parse platform-specific configurations."""
        configs = {}
        platform_dir = self.root_dir / "platform"
        
        for platform_path in platform_dir.glob("*"):
            if not platform_path.is_dir():
                continue
                
            detect_py = platform_path / "detect.py"
            if not detect_py.exists():
                continue
                
            platform = platform_path.name
            configs[platform] = self._parse_platform_detect(platform, detect_py)
            
        return configs
        
    def _parse_platform_detect(self, platform, detect_py):
        """Parse platform detection file."""
        config = {
            'name': platform,
            'defines': [],
            'libs': [],
            'includes': [],
            'flags': []
        }
        
        with open(detect_py) as f:
            content = f.read()
            
        # Extract flags and defines
        flags_match = re.search(r'def\s+get_flags\(\):\s*(.*?)(?=def|\Z)', content, re.DOTALL)
        if flags_match:
            flags_code = flags_match.group(1)
            config['flags'].extend(self._extract_list_items(flags_code))
            
        # Extract library dependencies
        libs_match = re.search(r'def\s+get_libs\(\):\s*(.*?)(?=def|\Z)', content, re.DOTALL)
        if libs_match:
            libs_code = libs_match.group(1)
            config['libs'].extend(self._extract_list_items(libs_code))
            
        return config
        
    def _parse_modules(self):
        """Parse module configurations."""
        modules = {}
        modules_dir = self.root_dir / "modules"
        
        for module_path in modules_dir.glob("*"):
            if not module_path.is_dir():
                continue
                
            module = module_path.name
            modules[module] = self._parse_module(module, module_path)
            
        return modules
        
    def _parse_module(self, module, module_path):
        """Parse a single module's configuration."""
        config = {
            'name': module,
            'sources': [],
            'deps': [],
            'defines': [],
            'includes': []
        }
        
        scsub = module_path / "SCsub"
        if scsub.exists():
            with open(scsub) as f:
                content = f.read()
                
            # Extract source files
            for line in content.split('\n'):
                if 'env.add_source_files' in line:
                    sources = self._extract_list_items(line)
                    config['sources'].extend(sources)
                    
            # Extract dependencies
            for line in content.split('\n'):
                if 'env.Depends' in line:
                    deps = self._extract_list_items(line)
                    config['deps'].extend(deps)
                    
        return config
        
    def _extract_list_items(self, text):
        """Extract items from a list in text."""
        items = []
        matches = re.finditer(r'\[(.*?)\]', text)
        for match in matches:
            items_str = match.group(1)
            items.extend([item.strip(' "\'') for item in items_str.split(',') if item.strip()])
        return items
        
    def _generate_root_cmakelists(self, options):
        """Generate root CMakeLists.txt."""
        content = [
            "cmake_minimum_required(VERSION 3.20)",
            "project(godot)",
            "",
            "# Global settings",
            "set(CMAKE_CXX_STANDARD 17)",
            "set(CMAKE_CXX_STANDARD_REQUIRED ON)",
            "set(CMAKE_POSITION_INDEPENDENT_CODE ON)",
            "",
            "# Options",
        ]
        
        # Add SCons options as CMake options
        for opt in options.values():
            if opt['type'] == 'bool':
                content.append(f'option({opt["name"]} "{opt["desc"]}" {str(opt["default"]).upper()})')
            elif opt['type'] == 'string':
                content.append(f'set({opt["name"]} "{opt["default"]}" CACHE STRING "{opt["desc"]}")')
            elif opt['type'] == 'enum':
                values_str = ';'.join(opt['values'])
                content.append(f'set({opt["name"]} "{opt["default"]}" CACHE STRING "{opt["desc"]}")')
                content.append(f'set_property(CACHE {opt["name"]} PROPERTY STRINGS {values_str})')
                
        # Add platform detection
        content.extend([
            "",
            "# Platform detection",
            "if(WIN32)",
            "    set(PLATFORM_NAME windows)",
            "elseif(APPLE)",
            "    set(PLATFORM_NAME macos)",
            "elseif(UNIX)",
            "    set(PLATFORM_NAME linuxbsd)",
            "endif()",
            "",
            "# Include platform-specific configuration",
            "include(cmake/platform_${PLATFORM_NAME}.cmake)",
            "",
            "# Add subdirectories",
            "add_subdirectory(core)",
            "add_subdirectory(drivers)",
            "add_subdirectory(main)",
            "add_subdirectory(modules)",
            "add_subdirectory(platform)",
            "add_subdirectory(scene)",
            "add_subdirectory(servers)",
            "",
            "# Main executable",
            "add_executable(godot",
            "    main/main.cpp",
            ")",
            "",
            "target_link_libraries(godot",
            "    PRIVATE",
            "    core",
            "    drivers",
            "    main",
            "    platform",
            "    scene",
            "    servers",
            "    ${CMAKE_THREAD_LIBS_INIT}",
            "    ${OPENGL_LIBRARIES}",
            "    ${X11_LIBRARIES}",
            "    ${ZLIB_LIBRARIES}",
            ")",
        ])
        
        cmake_file = self.root_dir / "CMakeLists.txt"
        with open(cmake_file, "w") as f:
            f.write("\n".join(content))
            
    def _generate_platform_cmake_files(self, configs):
        """Generate platform-specific CMake files."""
        cmake_dir = self.root_dir / "cmake"
        cmake_dir.mkdir(exist_ok=True)
        
        for platform, config in configs.items():
            content = [
                f"# Platform configuration for {platform}",
                "",
                "# Compiler flags",
            ]
            
            # Add platform-specific flags
            if config['flags']:
                content.append("add_compile_options(")
                for flag in config['flags']:
                    content.append(f"    {flag}")
                content.append(")")
                content.append("")
                
            # Add platform-specific defines
            if config['defines']:
                content.append("add_compile_definitions(")
                for define in config['defines']:
                    content.append(f"    {define}")
                content.append(")")
                content.append("")
                
            # Add platform-specific libraries
            if config['libs']:
                content.append("target_link_libraries(godot PRIVATE")
                for lib in config['libs']:
                    content.append(f"    {lib}")
                content.append(")")
                
            cmake_file = cmake_dir / f"platform_{platform}.cmake"
            with open(cmake_file, "w") as f:
                f.write("\n".join(content))
                
    def _generate_core_cmake_files(self):
        """Generate CMakeLists.txt for core libraries."""
        core_libs = ["core", "drivers", "main", "platform", "scene", "servers"]
        
        for lib in core_libs:
            lib_dir = self.root_dir / lib
            if not lib_dir.exists():
                continue
                
            content = [
                f"# {lib} library",
                "",
                "set(LIB_SOURCES",
            ]
            
            # Find source files
            sources = []
            for ext in ['*.cpp', '*.c', '*.h', '*.hpp', '*.inc']:
                for file in glob.glob(str(lib_dir / '**' / ext), recursive=True):
                    rel_path = os.path.relpath(file, str(lib_dir))
                    sources.append(f"    {rel_path}")
                    
            if sources:
                content.extend(sources)
                content.extend([
                    ")",
                    "",
                    f"add_library({lib} STATIC ${{LIB_SOURCES}})",
                ])
            else:
                print(f"Warning: No source files found for library {lib} in {lib_dir}")
                "",
                f"target_include_directories({lib}",
                "    PUBLIC",
                "        ${CMAKE_CURRENT_SOURCE_DIR}",
                "        ${CMAKE_SOURCE_DIR}",
                ")",
                "",
                "if(UNIX AND NOT APPLE)",
                f"    target_compile_definitions({lib}",
                "        PRIVATE",
                "        UNIX_ENABLED",
                "        X11_ENABLED",
                "        VULKAN_ENABLED",
                "        GLES3_ENABLED",
                "    )",
                "endif()",
            ]
            
            cmake_file = lib_dir / "CMakeLists.txt"
            with open(cmake_file, "w") as f:
                f.write("\n".join(content))
                
    def _generate_module_cmake_files(self, modules):
        """Generate module-specific CMake files."""
        modules_dir = self.root_dir / "modules"
        
        # Generate main modules/CMakeLists.txt
        content = [
            "# Godot modules",
            "",
        ]
        
        for module in modules:
            content.append(f"add_subdirectory({module})")
            
        cmake_file = modules_dir / "CMakeLists.txt"
        with open(cmake_file, "w") as f:
            f.write("\n".join(content))
            
        # Generate individual module CMakeLists.txt files
        for module, config in modules.items():
            content = [
                f"# {module} module",
                "",
                "set(MODULE_SOURCES",
            ]
            
            # Find source files
            module_dir = modules_dir / module
            sources = []
            for ext in ['*.cpp', '*.c', '*.h', '*.hpp', '*.inc']:
                for file in glob.glob(str(module_dir / '**' / ext), recursive=True):
                    rel_path = os.path.relpath(file, str(module_dir))
                    sources.append(f"    {rel_path}")
                    print(f"Found source file for module {module}: {rel_path}")
                    
            if sources:
                content.extend(sources)
                content.extend([
                    ")",
                    "",
                    f"add_library({module} STATIC ${{MODULE_SOURCES}})",
                    ""
                ])
            else:
                print(f"Warning: No source files found for module {module} in {module_dir}")
                
            # Add includes
            content.extend([
                f"target_include_directories({module}",
                "    PUBLIC",
                "        ${CMAKE_CURRENT_SOURCE_DIR}",
                "        ${CMAKE_SOURCE_DIR}",
                ")",
                "",
            ])
            
            # Add dependencies
            if config['deps']:
                content.append(f"target_link_libraries({module}")
                content.append("    PRIVATE")
                for dep in config['deps']:
                    content.append(f"        {dep}")
                content.append(")")
                
            cmake_file = modules_dir / module / "CMakeLists.txt"
            with open(cmake_file, "w") as f:
                f.write("\n".join(content))

def main():
    if len(os.sys.argv) != 2:
        print("Usage: scons_to_cmake.py <godot_root_dir>")
        return 1
        
    root_dir = os.sys.argv[1]
    if not os.path.isdir(root_dir):
        print(f"Error: {root_dir} is not a directory")
        return 1
        
    converter = SConsToCMakeConverter(root_dir)
    converter.convert()
    print("Done! CMake files have been generated.")
    return 0

if __name__ == "__main__":
    os.sys.exit(main())