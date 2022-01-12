#!/usr/bin/env bash
set -ex
cd "$(dirname "$0")"

output_folder="${1:-/tmp}"
mkdir -p "$output_folder"

# Function that builds the sphinx documentation.
# usage:    generate_docs <branch-name> <output-directory>
function generate_docs {
    if [ "$1" = "main" ]; then dir="docs"; else dir="$1/docs"; fi
    pushd ../
    python setup.py install
    sphinx-build -M html docs/source /tmp/sphinx-build
    rm -rf "$2/$dir"
    mv /tmp/sphinx-build/html "$2/$dir"
    popd
}

# Generate the documentation for the current branch
if curr_branch=$(git branch --show-current); then
    generate_docs "$curr_branch" "$output_folder"
fi
# Generate the documentation for the current tag
if curr_tag=$(git describe --tags --exact-match); then
    generate_docs "$curr_tag" "$output_folder"
fi

echo "Done generating documentation"

# Get all tags and branches for generating the index with links to docs for
# specific branches and versions:
git fetch
git fetch --tags

README="$output_folder/README.md"
echo "[Documentation](docs/index.html) for" \
     "[**$GITHUB_REPOSITORY**](https://github.com/$GITHUB_REPOSITORY)." \
> "$README"

