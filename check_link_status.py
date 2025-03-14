import os
import subprocess
import requests
import time
import sys  # Import the sys module


def fetch_and_check_status(url):
    """
    Fetches data from a URL and checks the HTTP status code.

    Args:
        url: The URL to fetch.

    Returns:
        True if the request was successful (status code 2xx) and the content is not empty,
        False otherwise.  Prints error messages to the console.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        if response.text:  # Check if response content is not empty
            print("Successfully fetched data!")
            return True
        else:
            print("Successfully fetched data, but the content is empty.")
            return False

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Request Exception: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False


if __name__ == "__main__":
    api_key = os.environ.get("HADITH_API_KEY")  # Replace with your actual API key
    url = f"https://hadithapi.com/api/al-silsila-sahiha/chapters?apiKey={api_key}"

    while True:
        print(f"Fetching data at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        success = fetch_and_check_status(url)

        if success:
            print("Script finished successfully.")
            subprocess.run(
                ["python", "C:\\Users\\User\\OneDrive\\Downloads\\hadith\\translate.py"]
            )
            sys.exit(0)  # Exit the script gracefully
        else:
            print("Trying again in 1 minutes...")
            time.sleep(60)  # Sleep for 5 minutes (300 seconds)
