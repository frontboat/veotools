"""Setup configuration for Veo Tools SDK."""

from setuptools import setup, find_packages

with open("VEO_TOOLS_README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="veo-tools",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="AI-powered video generation and stitching toolkit using Google's Veo models",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/veo-tools",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "google-genai>=0.1.0",
        "opencv-python>=4.8.0",
        "numpy>=1.24.0",
        "python-dotenv>=1.0.0",
        "requests>=2.31.0",
    ],
)