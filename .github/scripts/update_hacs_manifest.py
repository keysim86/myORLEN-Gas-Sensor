"""Update the manifest file."""
import json
import os
import sys


def update_manifest():
    """Update the manifest file."""
    version = "0.0.0"
    for index, value in enumerate(sys.argv):
        if value in ["--version", "-V"]:
            version = sys.argv[index + 1]

    with open(
        f"{os.getcwd()}/custom_components/myorlen_gas_sensor/manifest.json"
    ) as manifestfile:
        manifest = json.load(manifestfile)

    manifest["version"] = version

    # hassfest requires: domain first, name second, then alphabetical
    sorted_manifest = {}
    for key in ["domain", "name"]:
        if key in manifest:
            sorted_manifest[key] = manifest[key]
    for key in sorted(manifest.keys()):
        if key not in sorted_manifest:
            sorted_manifest[key] = manifest[key]

    with open(
        f"{os.getcwd()}/custom_components/myorlen_gas_sensor/manifest.json", "w"
    ) as manifestfile:
        manifestfile.write(json.dumps(sorted_manifest, indent=4))


update_manifest()