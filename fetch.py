import json
import requests


def fetch_hadith_data(url):
    """Fetches the JSON data from the given URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from URL: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return None


def display_hadith_table(data):
    """Displays the hadith data in a table format."""
    if not data or "hadiths" not in data or "data" not in data["hadiths"]:
        print("Invalid data format.")
        return

    hadiths = data["hadiths"]["data"]

    # Define the table headers
    headers = [
        "ID",
        "Hadith Number",
        "Status",
        "Nama Buku",
        "Penulis Buku",
        "Tajuk Hadith",
        "Perawi Melayu",
        "English Text",
        "Malay Translation",
        "Arabic Text",
    ]

    # Print the table header
    print("-" * 200)
    print("| " + "| ".join(headers) + "|")
    print("-" * 200)

    # Print each hadith as a row in the table
    for hadith in hadiths:
        row = [
            str(hadith["id"]),
            hadith["hadith_number"],
            hadith["status"],
            hadith["nama_buku"],
            hadith["penulis_buku"],
            hadith["tajuk_hadith"],
            hadith["perawi_melayu"],
            hadith["english_text"],
            hadith["malay_translation"],
            hadith["arabic_text"],
        ]
        # Adjust column width for better readability (optional)
        row = [
            item[:20] + "..." if len(item) > 20 else item for item in row
        ]  # Truncate long text
        print("| " + "| ".join(row) + "|")
    print("-" * 200)


# Main execution
if __name__ == "__main__":
    url = "https://doa-doa-api-ahmadramadhan.fly.dev/api"
    hadith_data = fetch_hadith_data(url)

    if hadith_data:
        # display_hadith_table(hadith_data)
        # save into file
        with open("doa.json", "w") as file:
            json.dump(hadith_data, file)
        print("Data saved to doa.json")
    else:
        print("No data to save.")
