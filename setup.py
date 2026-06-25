from setuptools import setup, find_packages

setup(
    name="dorkstrike",
    version="1.0.0",
    description="Advanced Google Dorking reconnaissance CLI tool",
    author="W1N7G0D",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "dorkstrike": ["data/*.json"],
    },
    install_requires=[
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=5.0.0",
    ],
    entry_points={
        "console_scripts": [
            "dorkstrike=dorkstrike:main",
        ],
    },
    python_requires=">=3.9",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Security",
    ],
)
