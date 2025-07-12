import os

from dotenv import load_dotenv

load_dotenv()  # This will load environment variables from a .env file if it exists


def get_env_var(var_name, default=None):
    env_var = os.getenv(var_name, default)
    if env_var in [None, ""]:
        print(f"{var_name} is not set; using default value: {default}")
        env_var = default
    return env_var


CONTROLLER = get_env_var("CONTROLLER", "None")
SITE = get_env_var("SITE", "None")
DEVICE_MAC = get_env_var("DEVICE_MAC", "None")
DEVICE_ID = get_env_var("DEVICE_ID", "None")

USERNAME = get_env_var("USERNAME", "None")
PASSWORD = get_env_var("PASSWORD", "None")

