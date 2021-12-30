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
        "amaranth~=0.3",
        "numpy~=1.21",
        "PyBoolector~=3.2",
    ],
    packages=find_packages(),
)
