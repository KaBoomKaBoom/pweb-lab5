#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Make go2web executable
chmod +x "$SCRIPT_DIR/go2web"

# Check if the script is already in PATH
if [ -f "/usr/local/bin/go2web" ]; then
    echo "go2web is already installed."
else
    # Create symbolic link to make go2web accessible from anywhere
    sudo ln -s "$SCRIPT_DIR/go2web" /usr/local/bin/go2web
    echo "go2web has been installed successfully!"
fi

echo "You can now use go2web from any directory."