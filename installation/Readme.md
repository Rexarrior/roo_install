
**Usage**:
```bash
python3 setup_roo.py \
  --key YOUR_OPENROUTER_API_KEY \
  --target_folder ./my_project \
  --config_folder ./custom_config
```

**Notes**:
1. Requires internet access for downloads
2. Needs sudo privileges for system package installation
3. Tested on Ubuntu/Debian-based systems
4. Automatically handles dependencies (will install required system packages)
5. Cleans up temporary files after installation

The script now performs all originally requested steps plus the additional MCP Playwright installation through npm. The installation order ensures all dependencies are met before proceeding to the next steps.