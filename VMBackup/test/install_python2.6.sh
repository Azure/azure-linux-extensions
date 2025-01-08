#!/bin/bash

# Function to print messages
print_message() {
    echo "----------------------------------------"
    echo "$1"
    echo "----------------------------------------"
}

# Check if Python 2.6 is already installed
if command -v python2.6 &> /dev/null; then
    PYTHON_VERSION=$(python2.6 --version 2>&1)  # Capture version output
    print_message "Python 2.6 is already installed. Version: $PYTHON_VERSION"
    exit 0
fi

# Update the package list
print_message "Updating package list..."
sudo apt update

# Install required packages for building Python
print_message "Installing required packages..."
if ! sudo apt install -y build-essential checkinstall \
libreadline-dev libncurses-dev libssl-dev \
libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev; then
    echo "Error: Failed to install required packages."
    exit 1
fi

print_message "Checking for libreadline installation..."
dpkg -l | grep libreadline || echo "libreadline not found."

print_message "Changing directory to /tmp..."
cd /tmp

print_message "Downloading Python 2.6.6 source code..."
if ! wget https://www.python.org/ftp/python/2.6.6/Python-2.6.6.tgz; then
    echo "Error: Failed to download Python 2.6.6 source code."
    exit 1
fi

# Extract the downloaded tarball
print_message "Extracting Python 2.6.6..."
if ! tar -xzf Python-2.6.6.tgz; then
    echo "Error: Failed to extract Python 2.6.6."
    exit 1
fi

# Change directory to the extracted folder
cd Python-2.6.6

print_message "Configuring Python build with optimizations..."
if ! ./configure --enable-optimizations; then
    echo "Error: Configuration of Python build failed."
    exit 1
fi

# Compile the source code
print_message "Compiling Python 2.6.6. This may take a while..."
if ! make; then
    echo "Error: Compilation of Python 2.6.6 failed."
    exit 1
fi

print_message "Installing Python 2.6..."
if ! sudo make altinstall; then
    echo "Error: Installation of Python 2.6 failed."
    exit 1
fi

print_message "Verifying the installation of Python 2.6..."
if command -v python2.6 &> /dev/null; then
    python2.6 --version
else
    echo "Error: Python 2.6 installation was not successful."
    exit 1
fi

print_message "Creating a symbolic link for python2..."
if ! sudo ln -s /usr/local/bin/python2.6 /usr/bin/python2; then
    echo "Error: Failed to create a symbolic link for python2."
    exit 1
fi

print_message "Python 2.6 installation completed successfully."
