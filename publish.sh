#!/bin/bash
__heredoc__="""
Script to publish a new version of xdoctest on PyPI

TODO:
    - [ ] Do a digital signature of release

Requirements:
     twine

Notes:
    # NEW API TO UPLOAD TO PYPI
    # https://packaging.python.org/tutorials/distributing-packages/

Usage:
    cd <YOUR REPO>

    git fetch --all
    git checkout master
    git pull 

    gitk --all

    ./publish

    git checkout -b dev/<next>
"""
if [[ "$USER" == "joncrall" ]]; then
    GITHUB_USERNAME=erotemic
fi

# First tag the source-code
VERSION=$(python -c "import setup; print(setup.parse_version())")
BRANCH=$(git branch | grep \* | cut -d ' ' -f2)

echo "=== PYPI PUBLISHING SCRIPT =="
echo "BRANCH = $BRANCH"
echo "VERSION = '$VERSION'"
echo "GITHUB_USERNAME = $GITHUB_USERNAME"

if [[ "$BRANCH" != "master" ]]; then
    echo "WARNING: you are running publish on a non-master branch"
fi

# Verify that we want to publish
read -p "Are you ready to publish version=$VERSION on branch=$BRANCH? (input 'yes' to confirm)" ANS
echo "ANS = $ANS"

if [[ "$ANS" == "yes" ]]; then
    echo "Live run"

    git tag $VERSION -m "tarball tag $VERSION"
    git push --tags origin master

    pip install twine -U

    # Build wheel or source distribution
    python setup.py bdist_wheel --universal
    WHEEL_PATH=$(ls dist/*-$VERSION-*.whl)
    echo "WHEEL_PATH = $WHEEL_PATH"

    gpg --detach-sign -a $WHEEL_PATH
    gpg --verify $WHEEL_PATH.asc $WHEEL_PATH 
    twine check $WHEEL_PATH.asc $WHEEL_PATH

    #echo "GITHUB_USERNAME = $GITHUB_USERNAME"
    #echo "TWINE_PASSWORD = $TWINE_PASSWORD"
    gpg --verify $WHEEL_PATH.asc $WHEEL_PATH 
    CMD="twine upload --username $GITHUB_USERNAME --password=$TWINE_PASSWORD --sign $WHEEL_PATH.asc $WHEEL_PATH"
    #echo "CMD = $CMD"
    $CMD
else  
    echo "Dry run"
fi
