#!/usr/bin/env bash
set -ex
cd "$(dirname "$0")"

output_folder="${1:-/tmp}"
mkdir -p "$output_folder"

# Function that builds the sphinx documentation.
# usage:    generate_docs <branch-name> <output-directory>
function generate_docs {
    if [ "$1" = "main" ]; then dir="Sphinx"; else dir="$1/Sphinx"; fi
    pushd ../
    python setup.py install
    sphinx-build -M html docs/sphinx/source /tmp/sphinx-build
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
echo "Documentation for" \
     "[**$GITHUB_REPOSITORY**](https://github.com/$GITHUB_REPOSITORY)." \
> "$README"
# Always have a link to main, it's at the root of the docs folder
echo -e '\n### Main Branch\n' >> "$README"
echo "- **main**  " >> "$README"
echo "  [Sphinx](Sphinx/index.html)" >> "$README"
# Find all tags with documentation (version numbers)
echo -e '\n### Tags and Releases\n' >> "$README"
git tag -l --sort=-creatordate \
 | while read tag; do
    index="$output_folder/$tag/Sphinx/index.html"
    if [ -e "$index" ]; then
        echo "- **$tag**  " >> "$README"
        echo "  [Sphinx]($tag/Sphinx/index.html)" >> "$README"
    else
        echo "tag $tag has no documentation"
    fi
done
# Find other branches (not version numbers)
echo -e '\n### Other Branches\n' >> "$README"
git branch -r --sort=-committerdate | cut -d / -f 2 \
 | while read branch
do
    index="$output_folder/$branch/Sphinx/index.html"
    if [ -e "$index" ]; then
        echo "- **$branch**  " >> "$README"
        echo "  [Sphinx]($branch/Sphinx/index.html)" >> "$README"
    else
        echo "branch $branch has no documentation"
    fi
done

echo -e "\n***\n" >> "$README"
# echo "<sup>Updated on $(date)</sup>" >> "$README"
cat > "$output_folder/_config.yml" << EOF
include:
  - "_modules"
  - "_sources"
  - "_static"
  - "_images"
EOF