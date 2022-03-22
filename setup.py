import setuptools

library_name = "dman"

print(setuptools.find_packages())

setuptools.setup(
    name=library_name,
    version="0.0.0",
    author="Peter Coppens",
    author_email='peter.coppens@kuleuven.be',
    description="Toolbox for experimental data management in Python",
    packages=setuptools.find_packages(),
    python_requires='>=3.8',
    extras_require = {'numpy': 'numpy'},
    scripts=['bin/dman']
)

# TODO add minimal requirements
