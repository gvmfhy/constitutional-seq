"""
Constitutional.seq - Principle-based canonical sequence selection for mRNA therapeutics

An AI-safety inspired approach to biological sequence retrieval.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="constitutional-seq",
    version="1.0.0",
    author="Austin P. Morrissey",
    author_email="austin.morrissey@proton.me",
    description="Principle-based canonical sequence retrieval for mRNA therapeutics",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/constitutional-seq",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "genbank_tool": ["gui/*.md"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "PyQt5>=5.15.0",
        "biopython>=1.79",
        "pandas>=1.3.0",
        "numpy>=1.20.0",
        "requests>=2.26.0",
        "urllib3>=1.26.0",
        "click>=8.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "mypy>=0.900",
        ],
        "demo": [
            "pyautogui>=0.9.50",
            "Pillow>=8.0.0",
        ],
        "docs": [
            "markdown>=3.3.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "constitutional-seq=genbank_tool.cli:cli",
            "constitutional-seq-gui=genbank_tool.gui.main_window:main",
        ],
    },
)