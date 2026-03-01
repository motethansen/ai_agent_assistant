#!/bin/bash
# Move to the directory where this script is located
cd "$(dirname "$0")"

# Ensure the main installer is executable
chmod +x install.sh

# Run the installer
./install.sh

# Keep the window open so the user can see the final message
echo ""
echo "Press any key to close this window..."
read -n 1 -s
