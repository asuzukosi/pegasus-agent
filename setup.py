from setuptools import setup
# testing

setup(
    name='src/pegasus',
    version='0.1.0',    
    description='A lightweight terminal agent framework',
    url='https://github.com/asuzukosi/pegasus',
    author='Asuzu Kosi',
    author_email='keloasuzu@yahoo.com',
    license='BSD 2-clause',
    packages=['pegasus'],
    install_requires=['anthropic', 'click', 'openai', 'retry', 'rich'],

    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',  
        'Operating System :: POSIX :: Linux',        
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
)