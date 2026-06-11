from setuptools import find_packages, setup

version_ns = {}
with open("core/version.py", "r", encoding="utf-8") as fh:
    exec(fh.read(), version_ns)

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="virtuoso-cli-agent",
    version=version_ns["__version__"],
    description="Virtuoso CLI Agent with local Shimmy, Gemini, and TUI support.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Virtuoso Open Source",
    python_requires=">=3.10",
    packages=find_packages(include=["core", "core.*", "virtuoso_tui", "virtuoso_tui.*", "virtuoso_web", "assets", "assets.*"]),
    py_modules=["virtuoso", "run_virtuoso"],
    install_requires=[
        "requests>=2.31.0",
        "PyYAML>=6.0",
        "textual>=0.52.1",
        "openai>=1.0.0",
        "google-genai>=1.0.0",
        "google-auth>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=9.0.3",
            "pyinstaller>=5.0",
            "Pillow>=10.0.0",
            "playwright>=1.50.0",
            "wheel>=0.42.0",
        ],
        "build": ["pyinstaller>=5.0", "Pillow>=10.0.0", "wheel>=0.42.0"],
    },
    entry_points={
        "console_scripts": [
            "virtuoso=virtuoso:cli_main",
            "run_virtuoso=run_virtuoso:main",
        ]
    },
    include_package_data=True,
    package_data={
        "virtuoso_web": ["dashboard.html"],
        "assets.icons": ["*.ico", "*.icns", "*.png"],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
