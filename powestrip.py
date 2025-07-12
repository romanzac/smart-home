import json
import logging
import urllib3
import requests
import argparse

from env_vars import USERNAME, PASSWORD, CONTROLLER, DEVICE_MAC, DEVICE_ID, SITE

# Configuration
RETRY_COUNT = 3  # Number of retries if state doesn't update
RETRY_DELAY = 2  # Seconds to wait between retries

# Set up logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Suppress InsecureRequestWarning for local development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def authenticate_controller():
    """Authenticate with the UniFi Controller and return a session object."""
    try:
        session = requests.Session()
        session.verify = False
        login_data = {"username": USERNAME, "password": PASSWORD}
        headers = {"Content-Type": "application/json"}
        response = session.post(
            f"https://{CONTROLLER}:443/api/auth/login",
            json=login_data,
            headers=headers
        )
        logging.debug(f"Login response status: {response.status_code}")
        logging.debug(f"Login response content: {response.text}")
        if response.status_code == 200:
            csrf_token = response.headers.get("X-CSRF-Token") or session.cookies.get("csrf_token")
            if csrf_token:
                session.headers.update({"X-CSRF-Token": csrf_token})
                logging.debug(f"Set X-CSRF-Token: {csrf_token}")
            logging.info("Successfully authenticated with UniFi Controller")
            return session
        else:
            logging.error(f"Authentication failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logging.error(f"Authentication error: {e}")
        return None

def get_device_info(session, site, mac, device_id):
    """Retrieve device information for the given device ID or MAC address."""
    try:
        response = session.get(
            f"https://{CONTROLLER}:443/proxy/network/api/s/{site}/stat/device",
            headers={"Content-Type": "application/json"}
        )
        logging.debug(f"Device list response status: {response.status_code}")
        logging.debug(f"Raw device list response: {response.text}")
        if response.status_code != 200:
            logging.error(f"Failed to retrieve devices: {response.status_code} - {response.text}")
            return None
        try:
            devices = response.json().get("data", [])
            for device in devices:
                if device.get("mac", "").lower() == mac.lower():
                    logging.info(f"Found USP-Strip via /stat/device: {json.dumps(device, indent=2)}")
                    return device
            logging.warning(f"Device with MAC {mac} not found")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error: {e}")
            return None
    except Exception as e:
        logging.error(f"Error retrieving devices: {e}")
        return None

def get_outlet_state(device, outlet_index):
    """Get the relay state of a specific outlet."""
    outlets = device.get("outlet_overrides", device.get("outlet_table", []))
    for outlet in outlets:
        if outlet.get("index") == outlet_index:
            return outlet.get("relay_state", False)
    logging.error(f"Outlet index {outlet_index} not found in outlet table")
    return None

def control_outlet(session, device_id, site, outlet_index, action):
    """Control a specific outlet on the USP-Strip using PUT with the provided payload structure."""
    try:
        state = True if action.lower() == "on" else False
        device = get_device_info(session, site, DEVICE_MAC, device_id)
        if not device:
            logging.error("Failed to fetch device info for control")
            return False
        outlet_overrides = device.get("outlet_overrides", device.get("outlet_table", []))
        for outlet in outlet_overrides:
            if outlet.get("index") == outlet_index:
                outlet["relay_state"] = state
                break
        else:
            logging.warning(f"Outlet index {outlet_index} not found, adding it with default values")
            outlet_overrides.append({"index": outlet_index, "name": f"Outlet {outlet_index}", "cycle_enabled": False, "relay_state": state})
        payload = {"outlet_overrides": outlet_overrides}
        logging.debug(f"Sending payload: {json.dumps(payload, indent=2)}")
        endpoint = f"/proxy/network/api/s/{site}/rest/device/{device_id}"
        response = session.put(
            f"https://{CONTROLLER}:443{endpoint}",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            verify=False
        )
        logging.debug(f"Outlet control response status: {response.status_code}")
        logging.debug(f"Outlet control response: {response.text}")
        if response.status_code == 200 and response.json().get("meta", {}).get("rc") == "ok":
            logging.info(f"Successfully sent {action} command for outlet {outlet_index} on device {device_id}")
            return True
        else:
            logging.error(f"Failed to control outlet: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logging.error(f"Error controlling outlet: {e}")
        return False

def verify_outlet_state(session, site, mac, device_id, outlet_index, desired_state):
    """Verify the outlet state after control command."""
    device = get_device_info(session, site, mac, device_id)
    if not device:
        logging.error("Failed to retrieve device info for state verification")
        return False
    current_state = get_outlet_state(device, outlet_index)
    if current_state is None:
        return False
    logging.info(f"Current outlet {outlet_index} state: {'on' if current_state else 'off'}")
    return current_state == desired_state

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Control outlets on a UniFi SmartPower Strip (USP-Strip).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-i", "--index",
        type=int,
        default=2,
        help="Outlet index to control (1-7)"
    )
    parser.add_argument(
        "-a", "--action",
        type=str,
        default="on",
        choices=["on", "off", "cycle"],
        help="Action to perform on the outlet (on, off, or cycle)"
    )
    args = parser.parse_args()

    # Authenticate with the UniFi Controller
    session = authenticate_controller()
    if not session:
        logging.error("Authentication failed, exiting")
        return

    # Get device information
    device = get_device_info(session, SITE, DEVICE_MAC, DEVICE_ID)
    if not device:
        logging.error("Could not find USP-Strip, exiting")
        return

    # Extract device ID
    device_id = device.get("_id", DEVICE_ID)
    logging.info(f"Device ID: {device_id}")

    # Verify outlet index
    outlets = device.get("outlet_overrides", device.get("outlet_table", []))
    if not any(outlet.get("index") == args.index for outlet in outlets):
        logging.error(f"Outlet index {args.index} not found in outlet table: {outlets}")
        return

    # Log initial outlet state
    initial_state = get_outlet_state(device, args.index)
    logging.info(f"Initial outlet {args.index} state: {'on' if initial_state else 'off'}")

    # Control outlet
    success = control_outlet(session, DEVICE_ID, SITE, args.index, args.action)
    if success:
        logging.info(f"Outlet {args.index} turned {args.action} successfully.")
    else:
        logging.error(f"Failed to turn outlet {args.index} {args.action}.")

if __name__ == "__main__":
    main()