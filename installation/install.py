#!/usr/bin/env python3
"""
Automate installation of Roo according to the logic described in Readme.md
"""

import os
import sys
import json
import shutil
import tempfile
import subprocess
import webbrowser
import urllib.request
import time
from pathlib import Path


def run_command(command, shell=False):
    """Run a shell command and return True if successful, False otherwise"""
    print(f'Running command: {command}')
    if shell:
        result = subprocess.run(command, shell=True, text=True, capture_output=True)
    else:
        result = subprocess.run(command, text=True, capture_output=True)

    if result.returncode != 0:
        print(f'Command failed with error: {result.stderr}')
        return False

    # Command succeeded - print output if any
    if result.stdout.strip():
        print(f'Command output: {result.stdout.strip()}')

    return True


class VSCodeManager:
    """Centralized VSCode detection and management"""

    def __init__(self):
        self.platform = sys.platform
        self._vscode_paths = self._get_vscode_paths()
        self._executable_paths = self._get_executable_paths()

    def _get_vscode_paths(self):
        """Get platform-specific VSCode installation paths"""
        if self.platform == 'darwin':  # macOS
            return [
                '/Applications/Visual Studio Code.app',
                '/Applications/Visual Studio Code - Insiders.app',
                os.path.expanduser('~/Applications/Visual Studio Code.app'),
                os.path.expanduser('~/Applications/Visual Studio Code - Insiders.app'),
            ]
        elif self.platform.startswith('linux'):  # Linux
            return [
                '/usr/share/code',
                '/opt/visual-studio-code',
                '/snap/code',
                os.path.expanduser('~/.local/share/code'),
            ]
        elif self.platform == 'win32':  # Windows
            return [
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'Microsoft VS Code'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Microsoft VS Code'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Microsoft VS Code'),
                os.path.join(os.environ.get('APPDATA', ''), 'Code'),
            ]
        return []

    def _get_executable_paths(self):
        """Get platform-specific VSCode executable paths"""
        if self.platform == 'darwin':  # macOS
            return [
                '/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code',
                '/Applications/Visual Studio Code - Insiders.app/Contents/Resources/app/bin/code',
                os.path.expanduser('~/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code'),
                os.path.expanduser('~/Applications/Visual Studio Code - Insiders.app/Contents/Resources/app/bin/code'),
            ]
        elif self.platform.startswith('linux'):  # Linux
            return [
                '/usr/bin/code',
                '/usr/local/bin/code',
                '/snap/bin/code',
                '/opt/visual-studio-code/bin/code',
                os.path.expanduser('~/.local/bin/code'),
            ]
        elif self.platform == 'win32':  # Windows
            return [
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'Microsoft VS Code', 'bin', 'code.cmd'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Microsoft VS Code', 'bin', 'code.cmd'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Microsoft VS Code', 'bin', 'code.cmd'),
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'Microsoft VS Code', 'Code.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Microsoft VS Code', 'Code.exe'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Microsoft VS Code', 'Code.exe'),
            ]
        return []

    def is_command_available(self):
        """Check if 'code' command is available"""
        return bool(run_command('which code', shell=True))

    def find_installation(self):
        """Find VSCode installation, returns (found, installation_path, executable_path)"""
        # First check if command is available
        if self.is_command_available():
            return True, 'command', 'code'

        # Check installation paths
        for path in self._vscode_paths:
            if os.path.exists(path):
                # Find corresponding executable
                executable = self.find_executable()
                return True, path, executable

        # Check for package manager installations on Linux
        if self.platform.startswith('linux'):
            if run_command('snap list | grep code', shell=True):
                return True, 'snap', '/snap/bin/code'
            if run_command('flatpak list | grep code', shell=True):
                return True, 'flatpak', 'flatpak run com.visualstudio.code'

        # Check Windows registry
        if self.platform == 'win32':
            if self._check_windows_registry():
                executable = self.find_executable()
                if executable:
                    return True, 'registry', executable

        return False, None, None

    def find_executable(self):
        """Find VSCode executable path"""
        for path in self._executable_paths:
            if os.path.exists(path):
                return path
        return None

    def _check_windows_registry(self):
        """Check Windows registry for VSCode installation"""
        try:
            import winreg

            registries = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]

            for registry in registries:
                try:
                    key = winreg.OpenKey(registry, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall')
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        subkey_name = winreg.EnumKey(key, i)
                        if 'Visual Studio Code' in subkey_name or 'code' in subkey_name.lower():
                            winreg.CloseKey(key)
                            return True
                    winreg.CloseKey(key)
                except:
                    continue
        except ImportError:
            pass
        return False


# Create global VSCode manager instance
vscode_manager = VSCodeManager()


def get_vscode_executable():
    """Get the VSCode executable path, trying 'code' command first, then native paths"""
    found, _, executable = vscode_manager.find_installation()
    return executable if found else None


def check_vscode_native_installation():
    """Check if VSCode is installed natively (without relying on 'code' command)"""
    found, install_path, _ = vscode_manager.find_installation()
    if found and install_path != 'command':
        print(f'VSCode found at: {install_path}')
        return True
    return False


def install_vscode():
    """Install Visual Studio Code"""
    print('Step 1: Installing Visual Studio Code...')

    # Check if VSCode is already installed via 'code' command
    if run_command('which code', shell=True):
        print('VSCode is already installed (code command available).')
        return True

    # Fallback: Check for native VSCode installation
    if check_vscode_native_installation():
        print('VSCode is installed and will be used directly.')
        return True

    # For macOS
    if sys.platform == 'darwin':
        # Try to install using Homebrew first
        if run_command('which brew', shell=True):
            run_command('brew install --cask visual-studio-code', shell=True)
        else:
            # Download and install manually
            print('Please install Homebrew or download VSCode manually from https://code.visualstudio.com/download')
            return False
    # For Linux
    elif sys.platform.startswith('linux'):
        # Try to install using apt (for Debian/Ubuntu)
        if run_command('which apt', shell=True):
            run_command('sudo apt update', shell=True)
            run_command('sudo apt install -y software-properties-common apt-transport-https wget', shell=True)
            run_command(
                'wget -q https://packages.microsoft.com/keys/microsoft.asc -O- | sudo apt-key add -', shell=True
            )
            run_command(
                'sudo add-apt-repository "deb [arch=amd64] https://packages.microsoft.com/repos/vscode stable main"',
                shell=True,
            )
            run_command('sudo apt update', shell=True)
            run_command('sudo apt install -y code', shell=True)
        else:
            print('Please install VSCode manually from https://code.visualstudio.com/download')
            return False
    # For Windows
    elif sys.platform == 'win32':
        print('Please install VSCode manually from https://code.visualstudio.com/download')
        return False

    # Verify installation - first try 'code' command
    if run_command('which code', shell=True):
        return True

    # Fallback: Check native installation again
    if check_vscode_native_installation():
        print('VSCode installed successfully but code command is not available.')
        print('You may need to enable the code command manually in VSCode.')
        return True

    print('Failed to install VSCode. Please install it manually.')
    return False


def install_auto_run_command_extension():
    """Install auto-run-command extension"""
    print('Step 2: Installing auto-run-command extension...')

    vscode_executable = get_vscode_executable()
    if not vscode_executable:
        print('Error: VSCode executable not found. Cannot install extension.')
        return False

    return run_command([vscode_executable, '--install-extension', 'gabrielgrinberg.auto-run-command'])


def install_roo_code_extension():
    """Install Roo Code extension"""
    print('Step 3: Installing Roo Code extension...')

    # URL to download the VSIX file
    vsix_url = (
        'https://github.com/Rexarrior/Roo-Code/releases/download/3.17.2_import_settings_command/roo-cline-3.17.2.vsix'
    )

    # Create a temporary directory for the download
    temp_dir = tempfile.mkdtemp()
    vsix_path = os.path.join(temp_dir, 'roo-cline.vsix')

    # Download the VSIX file with progress indicator
    print(f'Downloading Roo Code extension from {vsix_url}...')
    try:
        with urllib.request.urlopen(vsix_url) as response, open(vsix_path, 'wb') as out_file:
            # Get the total file size
            file_size = int(response.info().get('Content-Length', 0))

            if file_size > 0:
                print(f'Total size: {file_size / 1024 / 1024:.2f} MB')

                # Initialize variables for progress tracking
                downloaded = 0
                chunk_size = 8192
                progress_chars = 50  # Width of the progress bar

                # Download the file in chunks and show progress
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    downloaded += len(chunk)
                    out_file.write(chunk)

                    # Calculate and display progress
                    percent = int(downloaded * 100 / file_size)
                    filled_length = int(progress_chars * downloaded / file_size)
                    bar = '█' * filled_length + '-' * (progress_chars - filled_length)

                    # Use carriage return to update the same line
                    print(
                        f'\r|{bar}| {percent}% ({downloaded / 1024 / 1024:.2f}/{file_size / 1024 / 1024:.2f} MB)',
                        end='',
                    )

                # Print a newline after the progress bar is complete
                print()
            else:
                # If file size is unknown, just download without progress indicator
                print('File size unknown, downloading...')
                out_file.write(response.read())
                print('Download complete!')
    except Exception as e:
        print(f'\nError downloading VSIX file: {e}')
        return False

    # Check if the file was downloaded successfully
    if not os.path.exists(vsix_path) or os.path.getsize(vsix_path) == 0:
        print('Error: Failed to download VSIX file or file is empty')
        return False

    # Install the extension
    vscode_executable = get_vscode_executable()
    if not vscode_executable:
        print('Error: VSCode executable not found. Cannot install extension.')
        return False

    result = run_command([vscode_executable, '--install-extension', vsix_path])

    # Clean up the temporary directory
    shutil.rmtree(temp_dir)

    return result


def configure_auto_run_command(temp_dir, roo_settings_path):
    """Configure auto-run-command to run Roo Code import command"""
    print('Step 4: Configuring auto-run-command...')

    # Get VSCode settings directory
    if sys.platform == 'darwin':
        settings_dir = os.path.expanduser('~/Library/Application Support/Code/User')
    elif sys.platform.startswith('linux'):
        settings_dir = os.path.expanduser('~/.config/Code/User')
    elif sys.platform == 'win32':
        settings_dir = os.path.join(os.environ['APPDATA'], 'Code', 'User')
    else:
        print(f'Unsupported platform: {sys.platform}')
        return False

    # Create settings directory if it doesn't exist
    os.makedirs(settings_dir, exist_ok=True)

    # Path to settings.json
    settings_path = os.path.join(settings_dir, 'settings.json')

    # Load existing settings or create new ones
    if os.path.exists(settings_path):
        with open(settings_path, 'r') as f:
            try:
                settings = json.load(f)
            except json.JSONDecodeError:
                settings = {}
    else:
        settings = {}

    # Configure auto-run-command
    settings['auto-run-command.rules'] = [
        {
            'condition': 'always',
            'command': f'roo-cline.importSettings {roo_settings_path}',
            'message': "Running Roo Code's settings import",
            'delay': 5000,  # Add a 5-second delay to ensure extensions are loaded
        }
    ]

    # Save settings
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=4)

    return True


def get_oauth_token():
    """Open browser to get OAuth token"""
    print('Step 5: Getting OAuth token...')

    # Open browser
    oauth_url = 'https://oauth.yandex-team.ru/authorize?response_type=token&client_id=60c90ec3a2b846bcbf525b0b46baac80'
    webbrowser.open(oauth_url)

    # Ask user for OAuth token
    oauth_token = input('Please copy the OAuth token from the browser and paste it here: ')

    return oauth_token


def get_arcadia_root():
    """Get Arcadia root directory"""
    print('Step 6: Getting Arcadia root directory...')

    # Check if script is located within an Arcadia directory
    script_path = os.path.abspath(__file__)
    path_parts = script_path.split(os.sep)

    # Try to find 'arcadia' in the path
    try:
        arcadia_index = path_parts.index('arcadia')
        # Construct path to arcadia root
        arcadia_root = os.sep.join(path_parts[: arcadia_index + 1])
        print(f'Detected Arcadia root directory: {arcadia_root}')
        return arcadia_root
    except ValueError:
        # 'arcadia' not found in path, try 'arcadia2'
        try:
            arcadia_index = path_parts.index('arcadia2')
            # Construct path to arcadia root
            arcadia_root = os.sep.join(path_parts[: arcadia_index + 1])
            print(f'Detected Arcadia root directory: {arcadia_root}')
            return arcadia_root
        except ValueError:
            # Neither 'arcadia' nor 'arcadia2' found in path, ask user
            print('Could not automatically detect Arcadia root directory.')
            arcadia_root = input('Please provide the path to the Arcadia root directory: ')

            # Validate directory
            if not os.path.isdir(arcadia_root):
                print(f'Error: Directory not found: {arcadia_root}')
                return None

            return arcadia_root


def copy_config_files(source_dir, temp_dir):
    """Copy config files to temp directory"""
    print('Step 7: Copying config files to temp directory...')

    # Create temp directory if it doesn't exist
    os.makedirs(temp_dir, exist_ok=True)

    # Copy all files from config_files directory
    for file_name in os.listdir(source_dir):
        source_path = os.path.join(source_dir, file_name)
        dest_path = os.path.join(temp_dir, file_name)

        if os.path.isfile(source_path):
            shutil.copy2(source_path, dest_path)

    return True


def replace_placeholders(temp_dir, oauth_token, arcadia_root):
    """Replace placeholders in config files"""
    print('Step 8: Replacing placeholders in config files...')

    # Process all JSON files in temp directory
    for file_name in os.listdir(temp_dir):
        if file_name.endswith('.json'):
            file_path = os.path.join(temp_dir, file_name)

            # Read file content
            with open(file_path, 'r') as f:
                content = f.read()

            # Replace placeholders
            content = content.replace('{{OAUTH_PLACEHOLDER}}', oauth_token)
            content = content.replace('{{ARCADIA_PLACEHOLDER}}', arcadia_root)

            # Write updated content
            with open(file_path, 'w') as f:
                f.write(content)

    return True


def close_vscode_if_running():
    """Close VSCode if it's running"""
    print('Checking if VSCode is running...')

    # Different commands for different platforms
    if sys.platform == 'darwin':  # macOS
        # Check if VSCode is running
        ps_output = run_command('ps -A | grep -i "Visual Studio Code" | grep -v grep', shell=True)
        if ps_output:
            print('VSCode is running. Closing it...')
            run_command('pkill -f "Visual Studio Code"', shell=True)
            # Give it some time to close
            time.sleep(5)
            return True
    elif sys.platform.startswith('linux'):
        # Check if VSCode is running
        ps_output = run_command('ps -A | grep -i "code" | grep -v grep', shell=True)
        if ps_output:
            print('VSCode is running. Closing it...')
            run_command('pkill -f code', shell=True)
            # Give it some time to close
            time.sleep(5)
            return True
    elif sys.platform == 'win32':  # Windows
        # Check if VSCode is running
        ps_output = run_command('tasklist | findstr "Code.exe"', shell=True)
        if ps_output:
            print('VSCode is running. Closing it...')
            run_command('taskkill /F /IM Code.exe', shell=True)
            # Give it some time to close
            time.sleep(5)
            return True

    print('VSCode is not running.')
    return False


def run_vscode():
    """Run VSCode to import Roo configuration"""
    print('Step 9: Running VSCode to import Roo configuration...')

    close_vscode_if_running()

    # Run VSCode and wait for it to complete
    print('Launching new VSCode instance...')
    vscode_executable = get_vscode_executable()
    if not vscode_executable:
        print('Error: VSCode executable not found. Cannot launch VSCode.')
        return False

    process = subprocess.Popen([vscode_executable])

    # Ask user to close VSCode when import is complete
    input('VSCode is now running. Please wait for the Roo settings import to complete, then press Enter to continue...')

    # Ensure VSCode process is terminated
    try:
        process.terminate()
    except:
        pass

    return True


def remove_auto_run_command():
    """Remove auto-run-command extension and its configuration"""
    print('Step 10: Removing auto-run-command extension and its configuration...')

    # Uninstall extension
    vscode_executable = get_vscode_executable()
    if vscode_executable:
        run_command([vscode_executable, '--uninstall-extension', 'gabrielgrinberg.auto-run-command'])
    else:
        print('Warning: VSCode executable not found. Cannot uninstall extension automatically.')

    # Get VSCode settings directory
    if sys.platform == 'darwin':
        settings_dir = os.path.expanduser('~/Library/Application Support/Code/User')
    elif sys.platform.startswith('linux'):
        settings_dir = os.path.expanduser('~/.config/Code/User')
    elif sys.platform == 'win32':
        settings_dir = os.path.join(os.environ['APPDATA'], 'Code', 'User')
    else:
        print(f'Unsupported platform: {sys.platform}')
        return False

    # Path to settings.json
    settings_path = os.path.join(settings_dir, 'settings.json')

    # Load existing settings
    if os.path.exists(settings_path):
        with open(settings_path, 'r') as f:
            try:
                settings = json.load(f)
            except json.JSONDecodeError:
                settings = {}

        # Remove auto-run-command configuration
        if 'automate-run-command' in settings:
            del settings['auto-run-command.rules']

        # Save settings
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=4)

    return True


def merge_json_files(source_path, dest_path):
    """Merge source JSON into destination JSON without overwriting existing keys"""
    # Create parent directories if they don't exist
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    # Load source JSON
    with open(source_path, 'r') as f:
        source_data = json.load(f)

    # Load destination JSON if it exists, or create empty dict
    if os.path.exists(dest_path):
        with open(dest_path, 'r') as f:
            try:
                dest_data = json.load(f)
            except json.JSONDecodeError:
                dest_data = {}
    else:
        dest_data = {}

    # Merge source into destination (recursive function)
    def merge_dicts(source, dest):
        for key, value in source.items():
            if key not in dest:
                dest[key] = value
            elif isinstance(value, dict) and isinstance(dest[key], dict):
                merge_dicts(value, dest[key])
            # If key exists in both and is not a dict, keep the destination value

    # Perform the merge
    merge_dicts(source_data, dest_data)

    # Save merged data
    with open(dest_path, 'w') as f:
        json.dump(dest_data, f, indent=4)

    return True


def copy_roo_specific_files(temp_dir):
    """Copy Roo specific files"""
    print('Step 11: Copying Roo specific files...')

    # Get home directory
    home_dir = os.path.expanduser('~')

    # Merge mcp_global.json
    source_path = os.path.join(temp_dir, 'mcp_global.json')
    dest_path = os.path.join(
        home_dir,
        'Library/Application Support/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings/mcp_settings.json',
    )
    merge_json_files(source_path, dest_path)

    # Merge custom_modes.json
    source_path = os.path.join(temp_dir, 'custom_modes.json')
    dest_path = os.path.join(
        home_dir,
        'Library/Application Support/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings/custom_modes.json',
    )
    merge_json_files(source_path, dest_path)

    return True


def update_roo_code_extension():
    """Update RooCode extension from official repository"""
    print('Step 13: Updating RooCode extension from official repository...')

    # Run VSCode command to check for extension updates
    vscode_executable = get_vscode_executable()
    if not vscode_executable:
        print('Error: VSCode executable not found. Cannot update extension.')
        return False

    run_command([vscode_executable, '--force', '--install-extension', 'rooveterinaryinc.roo-cline'])

    return True


def remove_temp_files(temp_dir):
    """Remove temporary files"""
    print('Step 14: Removing temporary files...')

    # Remove temp directory
    shutil.rmtree(temp_dir)

    return True


def setup_virtual_environment(arcadia_root):
    """Setup virtual environment by calling separate script"""
    print('Step 15: Setting up Python virtual environment...')

    # Get path to setup_venv.py script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    setup_venv_script = os.path.join(script_dir, 'setup_venv.py')

    # Run the setup script
    setup_command = [sys.executable, setup_venv_script, arcadia_root]

    result = run_command(setup_command)
    if not result:
        print('Failed to setup virtual environment')
        return False

    print('Virtual environment setup completed successfully')
    return True


def create_env_file(arcadia_root, oauth_token):
    """Create .env file in project root"""
    print('Step 16: Creating .env file...')

    # Define the content for the .env file with the OAuth token as ELIZA_KEY
    env_content = f"""ELIZA_KEY={oauth_token}
STARTREK_TOKEN=
WIKI_TOKEN=
TELEGRAM_API_TOKEN=
"""

    # Path to the .env file in the project root
    mcp_dir = os.path.join(arcadia_root, 'taxi', 'ml', 'junk', 'junk', 'mcp')
    env_file_path = os.path.join(mcp_dir, '.env')

    try:
        # Check if file already exists
        if os.path.exists(env_file_path):
            print(f'.env file already exists at: {env_file_path}')
            print('Skipping creation to avoid overwriting existing configuration.')
            return True

        # Create the .env file
        with open(env_file_path, 'w') as f:
            f.write(env_content)

        print(f'.env file created successfully at: {env_file_path}')
        print('ELIZA_KEY has been set with your OAuth token.')
        print(
            'Note: You may need to update other tokens (STARTREK_TOKEN, WIKI_TOKEN, TELEGRAM_API_TOKEN) with your actual values.'
        )
        return True
    except Exception as e:
        print(f'Error creating .env file: {e}')
        return False


def main():
    """Main function"""
    print('Starting Roo installation...')

    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    print(f'Created temporary directory: {temp_dir}')

    try:
        # Step 1: Install VSCode
        if not install_vscode():
            print('Failed to install VSCode. Exiting...')
            return

        # Step 2: Install auto-run-command extension
        if not install_auto_run_command_extension():
            print('Failed to install auto-run-command extension. Exiting...')
            return

        # Step 3: Install Roo Code extension
        if not install_roo_code_extension():
            print('Failed to install Roo Code extension. Exiting...')
            return

        # Step 4: Get OAuth token
        oauth_token = get_oauth_token()
        if not oauth_token:
            print('Failed to get OAuth token. Exiting...')
            return

        # Step 5: Get Arcadia root directory
        arcadia_root = get_arcadia_root()
        if not arcadia_root:
            print('Failed to get Arcadia root directory. Exiting...')
            return

        # Step 6: Copy config files to temp directory
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config_files')
        if not copy_config_files(config_dir, temp_dir):
            print('Failed to copy config files. Exiting...')
            return

        # Step 7: Replace placeholders in config files
        if not replace_placeholders(temp_dir, oauth_token, arcadia_root):
            print('Failed to replace placeholders. Exiting...')
            return

        # Step 8: Configure auto-run-command
        roo_settings_path = os.path.join(temp_dir, 'roo-code-settings.json')
        if not configure_auto_run_command(temp_dir, roo_settings_path):
            print('Failed to configure auto-run-command. Exiting...')
            return

        # Step 9: Run VSCode
        if not run_vscode():
            print('Failed to run VSCode. Exiting...')
            return

        # Step 10: Remove auto-run-command
        if not remove_auto_run_command():
            print('Failed to remove auto-run-command. Exiting...')
            return

        # Step 11: Copy Roo specific files
        if not copy_roo_specific_files(temp_dir):
            print('Failed to copy Roo specific files. Exiting...')
            return

        # Step 12: MCP client building (skipped)
        print('Step 12: MCP client building skipped.')

        # Step 13: Update RooCode extension
        if not update_roo_code_extension():
            print('Failed to update RooCode extension. Exiting...')
            return

        # Step 14: Remove temp files
        if not remove_temp_files(temp_dir):
            print('Failed to remove temp files. Exiting...')
            return

        # Step 15: Setup virtual environment
        if not setup_virtual_environment(arcadia_root):
            print('Failed to setup virtual environment. Exiting...')
            return

        # Step 16: Create .env file
        if not create_env_file(arcadia_root, oauth_token):
            print('Failed to create .env file. Exiting...')
            return

        print('Roo installation completed successfully!')

    except Exception as e:
        print(f'An error occurred: {e}')
        # Clean up temp directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


if __name__ == '__main__':
    main()
