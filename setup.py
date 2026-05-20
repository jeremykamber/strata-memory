from setuptools import setup, find_packages

setup(
    name="strata-memory",
    version="0.1.0",
    description="Tiered memory system for AI agents with lifecycle management",
    packages=find_packages(include=["strata", "strata.*"]),
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "strata=strata.cli:main",
        ],
    },
)
