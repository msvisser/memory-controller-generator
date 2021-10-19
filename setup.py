from setuptools import setup, find_packages


setup(
    name="memory-controller-generator",
    version="0.1",
    description="An ECC memory controller generator",
    author="Michiel Visser",
    author_email="opensource@webmichiel.nl",
    license="",
    python_requires="~=3.6",
    install_requires=["nmigen>=0.2", "PyBoolector>=3.2", "numpy>=1.21"],
    packages=find_packages(),
)
