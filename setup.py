import os
import setuptools

class CleanCommand(setuptools.Command):
    """Custom clean command to tidy up the project root."""
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        os.system('rm -vrf ./build ./dist ./*.pyc ./*.tgz ./*.egg-info')

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
    cmdclass={
        'clean': CleanCommand,
    }
)

# TODO add minimal requirements
