import os
import re

# Mapping of file extensions to primary toolchain
EXTENSION_TO_TOOLCHAIN = {
    # Python
    ".py": "python",
    ".pyx": "python",  # Cython
    ".pyi": "python",  # Stub files
    
    # JavaScript/TypeScript
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    
    # C/C++
    ".c": "c",
    ".h": "c",  # Headers could be C or C++
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c++": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".hh": "cpp",
    
    # Java
    ".java": "java",
    ".kt": "java",  # Kotlin (uses JVM)
    ".kts": "java",
    ".scala": "java",  # Scala (uses JVM)
    
    # Rust
    ".rs": "rust",
    
    # PHP
    ".php": "php",
    ".phtml": "php",
    
    # Ruby
    ".rb": "ruby",
    ".rbw": "ruby",
    ".rake": "ruby",
    ".gemspec": "ruby",
    
    # Go
    ".go": "go",
    
    # Also detect common build/config files as secondary indicators
    "BUILD_FILE_INDICATORS": {
        "python": ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"],
        "javascript": ["package.json", "package-lock.json", "yarn.lock"],
        "typescript": ["tsconfig.json", "package.json"],
        "c": ["Makefile", "CMakeLists.txt", "configure"],
        "cpp": ["Makefile", "CMakeLists.txt", "configure"],
        "java": ["pom.xml", "build.gradle", "build.sbt"],
        "rust": ["Cargo.toml"],
        "php": ["composer.json"],
        "ruby": ["Gemfile", "Rakefile"],
        "go": ["go.mod", "go.sum", "Makefile"],
    }
}

def get_toolchains(repo_base_path: str, repo_name: str) -> list[str]:
    """
    Detect required toolchains for a repository by analyzing source file
    extensions and build configuration files.
    
    Args:
        repo_base_path: Base path where repositories are stored
        repo_name: Name of the repository directory
    
    Returns:
        List of unique toolchains required for the repository
    """
    repo_path = os.path.join(repo_base_path, repo_name)
    
    if not os.path.exists(repo_path):
        return []
    
    toolchains = set()
    
    # Walk through all files in the repository
    for root, dirs, files in os.walk(repo_path):
        # Skip common directories that might contain generated or third-party code
        dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', 'venv', 'env', 
                                                  '__pycache__', 'target', 'dist', 'build',
                                                  '.venv', 'vendor', 'bower_components'}]
        
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file)
            ext = ext.lower()
            
            # Check file extension for toolchain detection
            if ext in EXTENSION_TO_TOOLCHAIN:
                toolchains.add(EXTENSION_TO_TOOLCHAIN[ext])
            
    return sorted(list(toolchains))

def needs_clang(repo_path: str) -> bool:
    """
    检测repo是否需要clang编译器
    """
    indicators = {
        # 构建文件中显式指定clang
        "file_patterns": [
            ("Makefile", r"CC\s*=\s*clang"),
            ("Makefile", r"CXX\s*=\s*clang\+\+"),
            ("CMakeLists.txt", r"set\s*\(\s*CMAKE_C_COMPILER\s+clang"),
            ("CMakeLists.txt", r"set\s*\(\s*CMAKE_CXX_COMPILER\s+clang\+\+"),
            ("configure", r"CC=clang"),
            ("configure", r"CXX=clang\+\+"),
            (".clang", ""),  # clang配置文件存在
            ("compile_commands.json", ""),  # clang生成的编译数据库
        ],
        
        # 需要clang特定功能的文件
        "source_patterns": [
            (r"\.c$", r"__clang__"),  # 代码中使用了clang特定宏
            (r"\.cpp$", r"__clang__"),
            (r"\.h$", r"__attribute__\s*\(\s*\(.*?clang")  # clang特定属性
        ]
    }
    
    # 检查构建文件
    for filename, pattern in indicators["file_patterns"]:
        filepath = os.path.join(repo_path, filename)
        if os.path.exists(filepath):
            if not pattern:  # 文件存在即需要
                return True
            with open(filepath, 'r', errors='ignore') as f:
                if re.search(pattern, f.read(), re.MULTILINE):
                    return True
    
    # 检查源代码中的clang特征
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if file.endswith(('.c', '.cpp', '.h')):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', errors='ignore') as f:
                    content = f.read()
                    if re.search(r'#ifdef\s+__clang__', content):
                        return True
                    if re.search(r'#pragma\s+clang', content):
                        return True
    cargo_lock_path = os.path.join(repo_path, "Cargo.lock")
    if os.path.exists(cargo_lock_path):
        # 如果存在 Cargo.lock，就扫描它内部是否依赖了 clang-sys
        with open(cargo_lock_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if 'name = "clang-sys"' in content:
                # 一旦发现，就把 'clang' 加入依赖列表
                return True

    # 同样，扫描 Cargo.toml 也可以作为备选
    cargo_toml_path = os.path.join(repo_path, "Cargo.toml")
    if os.path.exists(cargo_toml_path):
        with open(cargo_toml_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # 检查是否直接或间接依赖了 cxx 或 bindgen 等 build-dependencies
            if any(dep in content for dep in ['clang-sys', 'cxx', 'bindgen']):
                return True
    
    return False

def get_env_setup(repo_base_path: str, repo_name: str) -> list[str]:
    repo_path = os.path.join(repo_base_path, repo_name)
    env_setup_scripts = []
                
    if needs_clang(repo_path): 
        env_setup_scripts.append("apt-get update && apt-get install clang libclang-dev -y")
    return env_setup_scripts
    