from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name = "dhampyr",
    version = "0.2.0.0",
    author = "sozuberry",
    author_email = "sozuberry@gmail.com",
    description = "Python simple validator for dict-like objects",
    long_description = long_description,
    long_description_content_type = "text/markdown",
    url = "https://github.com/sozu/py-dhampyr",
    packages = find_packages(),
    classifiers = [
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
