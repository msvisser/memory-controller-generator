from setuptools import setup, find_packages


setup(
    name="memory-controller-generator",
    version="0.1",
    description="An ECC memory controller generator",
    author="Michiel Visser",
    author_email="opensource@webmichiel.nl",
    license="",
    python_requires=">=3.6",
    install_requires=[
        "nmigen @ git+https://github.com/nmigen/nmigen.git@0b28a97ca00b44301fb35e2426d571e4f6640040#egg=nmigen",
        "numpy>=1.21",
        "PyBoolector>=3.2",
    ],
    packages=find_packages(),
)
