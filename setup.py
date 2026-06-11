from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="virtuoso-cli-agent",
    version="1.0.0",
    description="Virtuoso CLI Agent with local Shimmy, Gemini, and TUI support.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Virtuoso Open Source",
    python_requires=">=3.10",
    packages=find_packages(include=["core", "virtuoso_tui"]),
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
        "dev": ["pytest>=9.0.3", "pyinstaller>=5.0"],
    },
    entry_points={
        "console_scripts": [
            "virtuoso=virtuoso:main",
            "run_virtuoso=run_virtuoso:main",
        ]
    },
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
