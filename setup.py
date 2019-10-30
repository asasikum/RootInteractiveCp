from distutils.core import setup
import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    author_email='marian.ivanov@cern.ch',
    author='Marian Ivanov',
    url='https://github.com/miranov25/RootInteractive',
    name='RootInteractive',
    version='v0.00.15',
    #packages=setuptools.find_packages(),
    packages=setuptools.find_packages(exclude=["scripts*", "tests*"]),
    license='Not defined yet. Most probably similar to ALICE (CERN)  license',
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=[
        'numpy',
        'scipy',
        'pandas',
        'anytree',
        'pytest',
        'nbval',
        ## root dependencies
        'root_pandas'
        ##---------------------   graphics  dependencies
        'bokeh',
        'matplotlib',
        'plotly',
        'qgrid',
        'bqplot',
        'beakerx',
        # ----------------------   jupyter notebook dependencies
        'ipywidgets',
        'runtime',
        'request',
        # ---------------------    machine learning dependencies
        'sklearn',
        'scikit-garden',
        'scikit-hep',
        'forestci',
        'tensorflow',
        'keras',
        'skgarden',
        # ------------------      test and tutorials
        'pytest',
        'nbval',
        'nb-clean'
    ]
)
