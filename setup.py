from setuptools import setup

setup(
      name='johnny',
      packages=['johnny'],
      version='0.0.1',
      author='Andreas Grivas',
      author_email='andreasgrv@gmail.com',
      description='DEPendency Parsing library aka johnny',
      license='BSD',
      keywords=['parsing', 'dependency', 'language'],
      classifiers=[],
      install_requires=['chainer>=2.0.0', 'six', 'pyyaml', 'numpy>=1.13.0'],
      tests_require=['pytest']
      )
