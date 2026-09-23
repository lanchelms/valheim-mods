import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

import dotenv

# Load environment variables
dotenv.load_dotenv()

profile_dir_env = os.getenv("PROFILE_DIR")
assert profile_dir_env, "ERROR: PROFILE_DIR not found in .env file."
profile_dir = Path(profile_dir_env)
config_dir = profile_dir / "BepInEx" / "config"
sqlite_db_path = profile_dir.parent.parent.parent / "data.sqlite3"
assert config_dir.is_dir(), f"ERROR: The directory {config_dir} does not exist."
assert sqlite_db_path.is_file(), f"ERROR: Could not find {sqlite_db_path}."
repo_config = Path("./config")
toml_path = Path("thunderstore.toml")

print(f"Syncing config files from: {config_dir}")
shutil.rmtree(repo_config, ignore_errors=True)
shutil.copytree(
    config_dir,
    repo_config,
    ignore=shutil.ignore_patterns(
        "*.bin",
        "*.log",
        "*.old",
        "*.txt",
        "binds.yaml",
        "permissions.yaml",
        "LastSeasonChangeData",
        # Contains webhook URL that should not be on client
        "*AzuAntiCheat*",
        # Configured server side due to encryption key
        "org.bepinex.plugins.servercharacters.cfg",
        # Contains webhook URL that should not be on client
        "games.nwest.valheim.discordconnector",
        # Configured server side with increased limits, use default on client and allow
        # players to change config based on their Internet speeds if necessary
        "CW_Jesse.BetterNetworking.cfg",
        # Server devcommands aliases file
        "alias.yaml",
        # LetMeTameYou backup file
        "LetMeTameYou_DefaultTameList.yml.stock-backup",
    ),
)

mods_data = []
print(f"Opening database from: {sqlite_db_path}")
# copy because windows vs. wsl locking
with tempfile.NamedTemporaryFile() as tmp:
    # -wal, -shm, etc
    for f in sqlite_db_path.parent.glob(f"{sqlite_db_path.name}*"):
        suffix = f.name.replace(sqlite_db_path.name, "")
        shutil.copy2(f, tmp.name + suffix)
    with sqlite3.connect(tmp.name) as db_conn:
        cursor = db_conn.cursor()
        cursor.execute("SELECT mods FROM profiles WHERE name = ?;", (profile_dir.name,))
        mods_json_rows = cursor.fetchmany(2)
        assert len(mods_json_rows) == 1, f"ERROR: Expected 1 profile named {profile_dir.name}, found more."
        mods_json = mods_json_rows[0][0]
        mods_data = json.loads(mods_json)

dependencies = []
for mod in mods_data:
    full_name = mod["fullName"]
    if "Modpack" in full_name:
        continue
    name, _, version = mod["fullName"].rpartition("-")
    dependencies.append(f'"{name}" = "{version}"')
dependencies = sorted(dependencies)
print(f"Found {len(dependencies)} active dependencies: {'\n  '.join(dependencies)}")

print("Updating thunderstore.toml dependencies...")
with open(toml_path, "r", encoding="utf-8") as f:
    toml_lines = f.readlines()

new_toml_lines = []
for line in toml_lines:
    new_toml_lines.append(line)
    # Copy everything exactly as is, until we hit the dependencies header
    if line.strip() == "[package.dependencies]":
        break

# Append our dynamically generated list of active mods
for dep in dependencies:
    new_toml_lines.append(f"{dep}\n")

with open(toml_path, "w", encoding="utf-8") as f:
    f.writelines(new_toml_lines)

print(f"Success! Synced configs and updated {len(dependencies)} dependencies.")
