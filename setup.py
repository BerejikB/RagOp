from setuptools import find_packages, setup
import pathlib

def get_version():
    # read version from __init__ if defined else default
    init_path = pathlib.Path('rag/__init__.py')
    for line in init_path.read_text().splitlines():
        if line.startswith('__version__'):  
            return eval(line.split('=')[1])
    return '0.1.0'

setup(
    name='goose-rag',
    version=get_version(),
    description='Lightweight BM25-based RAG for Goose/KMGR to prevent context overflow',
    packages=find_packages(include=['rag']),
    python_requires=">=3.9",
)
