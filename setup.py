from setuptools import find_packages, setup

setup(
    name='sem-emergency-stop',
    version='1.3.2',
    author='GetYourGuide GmbH',
    description='Quickly stop all Google Ads advertising',
    license='Apache License, Version 2.0',
    license_file='LICENSE',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/getyourguide/sem-emergency-stop',
    packages=find_packages(),
    include_package_data=True,
    python_requires='>=3.8',
    install_requires=[
        'google-ads==15.0.0',
    ],
    entry_points={
        'console_scripts': [
            'sem-emergency-stop = ses.main:run',
            'ses-create-org-token = ses.auth:create_org_token',
            'ses-reset-auth = ses.auth:reset_auth',
        ],
    },
)
