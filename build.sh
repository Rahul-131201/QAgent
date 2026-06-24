#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing Playwright Chromium browser..."
# We remove --with-deps because Render's build environment does not allow sudo/root access.
# Render's base image typically has the necessary dependencies for headless Chromium already.
playwright install chromium
