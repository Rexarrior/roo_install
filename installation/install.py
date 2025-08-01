import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

def run_command(command, capture_output=False):
    """Run a shell command with error handling."""
    try:
        result = subprocess.run(
            command,
            check=True,
            text=True,
            stdout=subprocess.PIPE if capture_output else sys.stdout,
            stderr=subprocess.PIPE if capture_output else sys.stderr
        )
        return result.stdout.strip() if capture_output else ""
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(command)}")
        print(f"Error message: {e.stderr if capture_output else 'See above'}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Setup Roo Development Environment')
    parser.add_argument('--key', required=True, help='OpenRouter API key')
    parser.add_argument('--target_folder', required=True, help='Target directory for configuration')
    parser.add_argument('--config_folder', required=True, help='Source configuration directory')
    args = parser.parse_args()

    # Convert to Path objects
    config_folder = Path(args.config_folder)
    target_folder = Path(args.target_folder)
    target_folder.mkdir(parents=True, exist_ok=True)

    # Step 2-3: Load configuration files
    with open('./config/base_config.json') as f:
        base_config = json.load(f)
    
    with open('./config/base_mcp_config.json') as f:
        base_mcp_config = json.load(f)

    # Step 4: Replace API key
    if 'openrouter' in base_config and 'api_key' in base_config['openrouter']:
        base_config['openrouter']['api_key'] = args.key
    else:
        # Fallback to root-level key
        base_config['openrouter_api_key'] = args.key

    # Step 5: Replace system prompt
    system_prompt_file = config_folder / '.ai_system_prompt'
    if system_prompt_file.exists():
        with open(system_prompt_file) as f:
            system_prompt = f.read().strip()
        # Update both possible locations in config
        base_config['system_prompt'] = system_prompt
        if 'context' in base_config:
            base_config['context'] = system_prompt

    # Step 6: Copy AI memory bank
    memory_bank = config_folder / 'ai_memory_bank'
    if memory_bank.exists():
        shutil.copytree(memory_bank, target_folder / 'ai_memory_bank', dirs_exist_ok=True)

    # Step 7: Copy .roorules
    roorules = config_folder / '.roorules'
    if roorules.exists():
        shutil.copy2(roorules, target_folder)

    # Step 8: Write roo_settings.json
    with open(target_folder / 'roo_settings.json', 'w') as f:
        json.dump(base_config, f, indent=2)

    # Step 9: Write global MCP config
    mcp_path = Path.home() / '.config' / 'Code' / 'User' / 'globalStorage' / 'rooveterinaryinc.roo-cline' / 'settings'
    mcp_path.mkdir(parents=True, exist_ok=True)
    with open(mcp_path / 'mcp_settings.json', 'w') as f:
        json.dump(base_mcp_config, f, indent=2)

    # Step 10: Install VS Code
    deb_url = "https://go.microsoft.com/fwlink/?LinkID=760868"
    deb_path = "/tmp/vscode.deb"
    
    if not shutil.which("code"):
        print("Installing VS Code...")
        run_command(["wget", deb_url, "-O", deb_path])
        run_command(["sudo", "dpkg", "-i", deb_path])
        run_command(["sudo", "apt", "install", "-f", "-y"])
        os.unlink(deb_path)
        print("VS Code installed successfully")
    else:
        print("VS Code already installed")

    # Step 11: Install Roo extension
    print("Installing Roo extension...")
    run_command(["code", "--install-extension", "rooveterinaryinc.roo-cline"])

    # New Step: Install Node.js and npm
    print("Checking Node.js and npm installation...")
    if not shutil.which("node") or not shutil.which("npm"):
        print("Installing Node.js and npm...")
        run_command(["sudo", "apt", "update"])
        run_command(["sudo", "apt", "install", "-y", "nodejs", "npm"])
        print("Node.js and npm installed successfully")
    else:
        print("Node.js and npm already installed")

    # New Step: Install MCP Playwright globally
    print("Installing MCP Playwright...")
    run_command(["sudo", "npm", "install", "-g", "mcp-playwright@latest"])
    print("MCP Playwright installed globally")

    # Final validation
    print("\nSetup completed successfully!")
    print(f"Configuration files created in: {target_folder}")
    print(f"VS Code extension installed: rooveterinaryinc.roo-cline")
    print("Global packages installed: nodejs, npm, mcp-playwright")

if __name__ == "__main__":
    main()
