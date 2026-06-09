from setuptools import setup, find_packages

setup(
    name="strata-memory",
    version="0.2.0",
    description="Tiered memory system for AI agents with lifecycle management",
    packages=find_packages(include=["strata", "strata.*"]),
    package_data={
        "strata": ["skills/strata/SKILL.md", "skills/pi/strata.ts"],
    },
    include_package_data=True,
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "strata=strata.cli:main",
        ],
    },
)
