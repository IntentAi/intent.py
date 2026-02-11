from setuptools import setup, find_packages

setup(
    name='intent.py',
    version='0.1.0',
    description='Python bot SDK for Intent (discord.py compatible)',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='IntentAi',
    author_email='noreply@intent.chat',
    url='https://github.com/IntentAi/intent.py',
    packages=find_packages(),
    install_requires=[
        'aiohttp>=3.8.0',
        'msgpack>=1.0.0',
    ],
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    keywords='intent bot discord chat',
)
