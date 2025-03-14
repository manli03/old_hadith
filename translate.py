import requests
from google import genai
import json
import time
from typing import List, Dict, Optional, Any
import sys  # For writing loading animation to console
import threading
import os  # For creating directories
import subprocess
import signal


def signal_handler(sig, frame):
    print("You pressed Ctrl+C!")
    # Save the error hadith numbers to a JSON file
    if error_hadith_numbers:
        with open("hadiths/error_hadiths.json", "w", encoding="utf-8") as f:
            json.dump(error_hadith_numbers, f, indent=2, ensure_ascii=False)
        print(
            f"Error Hadith Numbers saved to: hadiths/error_hadiths.json"
        )  # Inform user
    else:
        print("No Error Hadiths found.")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def translate_hadith(
    hadith_data: Dict[str, Any],
    gemini_api_key: str,
    prompt: str,
    model_name: str = "gemini-1.5-flash-8b",
) -> Optional[Dict[str, Any]]:
    # """Translates a single Hadith data from English to Malay using Google Gemini."""

    client = genai.Client(api_key=gemini_api_key)
    combined_prompt = f"{prompt}\n\nData: {json.dumps(hadith_data, ensure_ascii=False)}"

    try:
        response = client.models.generate_content(
            model=model_name, contents=combined_prompt
        )

        # Added check to remove leading/trailing backticks and 'json' if present
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        try:
            translated_data = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"JSONDecodeError: {e}\nRaw Response: {response.text}")
            return None

        return translated_data

    except Exception as e:
        # Re-raise exception so process_hadiths can handle it.
        raise e


def fetch_hadith_data(
    api_url: str, chapter_number: int = None
) -> Optional[Dict[str, Any]]:  # Adjusted to return total count
    # """Fetches Hadith data from the specified API endpoint."""
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()

        return data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        raise e
    except (
        KeyError,
        json.JSONDecodeError,
    ) as e:  # Added more specific exception handling
        print(f"Error parsing API response: {e}")
        return None


def process_hadiths(
    api_url: str,
    gemini_api_key: str,
    prompt: str,
    error_hadith_numbers: list,
    model_index: int,
    models: List[str],
    resource_exhausted_count: int,
    start_index: int = 0,
    all_hadiths_data: List[Dict[str, Any]] = None,
) -> tuple[Optional[List[Dict[str, Any]]], int, int]:
    # """
    # Fetches Hadith data, translates each Hadith, and returns a list of translated Hadiths.
    # """
    if all_hadiths_data is None:
        hadith_data = fetch_hadith_data(api_url)
        if (
            not hadith_data
            or "hadiths" not in hadith_data
            or "data" not in hadith_data["hadiths"]
            or not isinstance(hadith_data["hadiths"]["data"], list)
        ):
            print("No valid Hadith data found.")
            return None, model_index, resource_exhausted_count

        hadith_data = hadith_data["hadiths"]["data"]
    else:
        hadith_data = all_hadiths_data

    translated_hadiths = []
    total_hadiths = len(hadith_data)
    successful_translations = 0

    print(f"Translating {total_hadiths} Hadiths...")

    i = start_index

    while i < total_hadiths:
        hadith = hadith_data[i]
        if isinstance(hadith, dict):
            hadith_id = hadith.get("id", "N/A")
            hadith_number = hadith.get("hadithNumber", "N/A")  # Get Hadith number
            print(
                f"  Translating Hadith {i + 1}/{total_hadiths} (ID: {hadith_id}, Number: {hadith_number})...",
                end="",
            )

            loading_chars = ["\\", "|", "/", "-"]
            stop_loading = False  # Flag to stop loading animation
            loading_char_index = 0

            def animate_loading():  # Function to create loading animation
                nonlocal loading_char_index
                while not stop_loading:
                    sys.stdout.write(
                        f"\r  Translating Hadith {i + 1}/{total_hadiths} (ID: {hadith_id}, Number: {hadith_number})... {loading_chars[loading_char_index % len(loading_chars)]}"
                    )
                    sys.stdout.flush()
                    time.sleep(0.2)
                    loading_char_index += 1

            # Start the thread
            loading_thread = threading.Thread(target=animate_loading)
            loading_thread.daemon = True
            loading_thread.start()

            # Prepare data for translation, only include what's necessary for the prompt
            translation_data = {
                "id": hadith.get("id", ""),
                "english_text": hadith.get("hadithEnglish", ""),
                "arabic_text": hadith.get("hadithArabic", ""),
                "narrator": hadith.get("englishNarrator", ""),
                "urduNarrator": hadith.get("urduNarrator", ""),
                "book_name": hadith.get("book", {}).get("bookName", ""),
                "writerName": hadith.get("book", {}).get("writerName", ""),
                "status": hadith.get("status", ""),
                "hadith_number": hadith_number,
            }

            translated_hadith = None  # Initialize
            attempts = 0
            while translated_hadith is None and attempts < 5:  # Try max 5 times
                if attempts > 0:
                    print(
                        f"  Retrying Hadith (Number: {hadith_number}) attempt [{attempts}/4] in 10 seconds..."
                    )
                    time.sleep(10)  # Wait before retrying

                try:
                    translated_hadith = translate_hadith(
                        translation_data,
                        gemini_api_key,
                        prompt,
                        model_name=models[model_index],
                    )
                except Exception as e:
                    if "429 RESOURCE_EXHAUSTED" in str(e):
                        resource_exhausted_count += 1
                        print(
                            f"  Resource exhausted. Count: {resource_exhausted_count}"
                        )
                        if resource_exhausted_count >= 4:
                            model_index = (model_index + 1) % len(
                                models
                            )  # Switch model
                            print(f"  Switching to model: {models[model_index]}")
                            resource_exhausted_count = 0  # Reset counter
                        else:
                            print(
                                "Waiting 5 seconds before retrying with the same model..."
                            )
                            time.sleep(5)  # Wait before retrying with the same model
                        continue  # Continue to the next retry attempt with potentially a new model.
                    else:
                        print(f"  Other Error during translation: {e}")
                        break  # Break retry loop for unhandled errors
                attempts += 1

            stop_loading = True  # Stop the animation when complete
            loading_thread.join()  # Join the thread, ensuring main thread waits until thread closes
            sys.stdout.write(
                f"\r  Translating Hadith {i + 1}/{total_hadiths} (ID: {hadith_id}, Number: {hadith_number})..."
            )  # Overwrite the animation
            sys.stdout.flush()  # Flush stream so it won't show

            if translated_hadith:
                # Include arabic_text in the translated output
                arabic_text = hadith.get(
                    "hadithArabic", ""
                )  # Get arabic_text if available
                translated_hadith["arabic_text"] = arabic_text

                translated_hadiths.append(translated_hadith)
                successful_translations += 1
                print(" Success!")
                resource_exhausted_count = 0  # Reset if success
            else:
                print(" Failed.")
                print(
                    f"    Failed to translate hadith with id: {hadith.get('id', 'N/A')}"
                )
                error_hadith_numbers.append(hadith_number)  # Store the hadith number
                resource_exhausted_count = 0  # Reset if fail
            time.sleep(1)  # Add a delay to avoid overwhelming the API
        else:
            print(f"Skipping invalid hadith entry: {hadith}")
        i += 1
    print(f"\nTranslation complete.")
    print(
        f"  Successfully translated: {successful_translations}/{total_hadiths} Hadiths."
    )

    if successful_translations == 0:
        return (
            None,
            model_index,
            resource_exhausted_count,
        )  # Return None only if absolutely no translations succeeded.
    return translated_hadiths, model_index, resource_exhausted_count


def get_chapter_count(book_slug: str, api_key: str) -> Optional[int]:
    # """Fetches the number of chapters for a given book."""
    url = f"https://hadithapi.com/api/{book_slug}/chapters?apiKey={api_key}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if (
            "chapters" in data
            and isinstance(data["chapters"], list)
            and len(data["chapters"]) > 0
        ):
            # Get the last chapter object in the list
            last_chapter = data["chapters"][-1]
            # Extract the 'chapterNumber' from the last chapter, which represents the total chapter count
            total_chapters = last_chapter.get("chapterNumber")
            if total_chapters is not None:
                return int(total_chapters)  # Ensure it's an integer
            else:
                print(f"Could not find 'id' in last chapter object for {book_slug}")
                return None

        else:
            print(f"Unexpected response for {book_slug} chapters: {data}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error fetching chapter count for {book_slug}: {e}")
        raise e
    except (KeyError, json.JSONDecodeError) as e:
        print(f"Error parsing chapter count for {book_slug}: {e}")
        return None


def process_book(
    book_slug: str,
    book_name: str,
    api_key: str,
    gemini_api_key: str,
    prompt: str,
    error_hadith_numbers: list,
    chapterNumber: int = 1,
    model_index: int = 0,
):
    # """Processes all chapters of a book, fetches hadiths, translates them, and saves to JSON files."""
    chapter_count = get_chapter_count(book_slug, api_key)

    if chapter_count is None:
        print(f"Failed to get chapter count for {book_name}.")
        return

    print(f"Processing {book_name} with {chapter_count} chapters.")

    # Initialize model-related variables *outside* the chapter loop
    # model_index = 0
    models = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-thinking-exp-01-21",
        "gemini-1.5-flash-8b",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
    ]
    resource_exhausted_count = 0

    for chapter_number in range(chapterNumber, chapter_count + 1):
        print(f"Processing {book_name} - Chapter {chapter_number}/{chapter_count}")
        book_dir = f"hadiths/{book_slug.replace(' ', '-').lower()}"
        filename = f"{book_dir}/chapter_{chapter_number}.json"

        hadith_api_url = f"https://hadithapi.com/public/api/hadiths?apiKey={api_key}&book={book_slug}&chapter={chapter_number}&paginate=1000"

        # Fetch all hadiths for the chapter from the API to get the total count
        all_hadiths_data_response = fetch_hadith_data(hadith_api_url)

        if not all_hadiths_data_response or "hadiths" not in all_hadiths_data_response:
            print(
                f"Failed to fetch all hadiths data for {book_name} - Chapter {chapter_number}."
            )
            continue  # Skip to the next chapter

        total_hadiths_in_chapter = all_hadiths_data_response["hadiths"]["total"]
        print(
            f"Total Hadiths in {book_name} - Chapter {chapter_number}: {total_hadiths_in_chapter}"
        )

        # Check if the JSON file already exists
        if os.path.exists(filename):
            print(
                f"JSON file already exists for {book_name} - Chapter {chapter_number}. Checking for missing hadiths..."
            )
            # Load existing hadiths
            with open(filename, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                existing_hadiths = existing_data["hadiths"]["data"]

                # Remove hadiths that have any "" or null value in any of the fields and refetch it from api
                # Convert Hadith IDs to Integer if they are strings
                # Remove hadiths that cannot convert to int
                valid_hadiths = []
                isBroken = False
                for hadith in existing_hadiths:
                    if any(value == "" for value in hadith.values()):  # Check if any value is empty string
                        # do it here
                        print(
                            f"Defect hadith: ID '{hadith.get('id')}'"
                        )
                        isBroken = True
                        continue
                    elif isinstance(hadith.get("id"), str):
                        try:
                            hadith["id"] = int(hadith["id"])
                            valid_hadiths.append(hadith)
                        except ValueError:
                            print(
                                f"Warning: Could not convert Hadith ID '{hadith.get('id')}' to integer. Removing hadith from data."
                            )
                            isBroken = True
                            continue  # Skip to the next hadith
                    else:
                        valid_hadiths.append(hadith)

                # Update the JSON with the new structure
                updated_data = {
                    "status": 200,
                    "message": "Hadiths has been found.",
                    "hadiths": {
                        "total": total_hadiths_in_chapter,
                        "data": valid_hadiths,
                    },
                }

                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(updated_data, f, indent=2, ensure_ascii=False)

                existing_data = (
                    updated_data  # Update existing_data for subsequent checks
                )

                existing_ids = {hadith["id"] for hadith in existing_hadiths}

            if isBroken:
                # Rerun the method
                process_book(
                    book_slug,
                    book_name,
                    api_key,
                    gemini_api_key,
                    prompt,
                    error_hadith_numbers,
                    chapterNumber=chapter_number,
                    model_index=model_index,
                )  
                return
            # Fetch all hadiths data
            all_hadiths_data = all_hadiths_data_response["hadiths"]["data"]

            # Identify missing hadiths based on 'id'
            missing_hadiths_data = [
                hadith
                for hadith in all_hadiths_data
                if hadith["id"] not in existing_ids
            ]

            if missing_hadiths_data:
                print(f"Found {len(missing_hadiths_data)} missing hadiths.")

                # Translate only the missing hadiths
                (
                    translated_missing_hadiths,
                    model_index,
                    resource_exhausted_count,
                ) = process_hadiths(
                    hadith_api_url,
                    gemini_api_key,
                    prompt,
                    error_hadith_numbers,
                    model_index,
                    models,
                    resource_exhausted_count,
                    all_hadiths_data=missing_hadiths_data,
                )

                if translated_missing_hadiths:
                    print(
                        "Successfully translated missing hadiths. Appending to existing JSON."
                    )

                    # Append the translated missing hadiths to the existing data
                    existing_hadiths.extend(translated_missing_hadiths)

                    # Sort hadiths by ID
                    existing_hadiths.sort(key=lambda x: int(x["id"]))
                    existing_data["hadiths"]["data"] = existing_hadiths

                    # Save the updated JSON file
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(existing_data, f, indent=2, ensure_ascii=False)
                    print(f"Appended translated hadiths to {filename}")
                else:
                    print(
                        "No missing hadiths were translated for {book_name} - Chapter {chapter_number}."
                    )
            else:
                print(
                    f"No missing hadiths found in {book_name} - Chapter {chapter_number}."
                )
            # sys.exit(0)

            continue  # Skip to the next chapter after checking and appending.

        # If the JSON file does not exist, translate and save all hadiths for the chapter
        all_hadiths_data = all_hadiths_data_response["hadiths"]["data"]
        translated_hadiths, model_index, resource_exhausted_count = process_hadiths(
            hadith_api_url,
            gemini_api_key,
            prompt,
            error_hadith_numbers,
            model_index,
            models,
            resource_exhausted_count,
            all_hadiths_data=all_hadiths_data,
        )

        if translated_hadiths:
            # Create a directory for the book if it doesn't exist
            book_dir = f"hadiths/{book_slug.replace(' ', '-').lower()}"
            os.makedirs(book_dir, exist_ok=True)

            # Save to a JSON file named after the chapter
            filename = f"{book_dir}/chapter_{chapter_number}.json"
            # Create the structure
            output_data = {
                "status": 200,
                "message": "Hadiths has been found.",
                "hadiths": {
                    "total": total_hadiths_in_chapter,
                    "data": translated_hadiths,
                },
            }

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            print(f"Saved translated hadiths to {filename}")
        else:
            print(f"No hadiths translated for {book_name} - Chapter {chapter_number}.")


# Configuration
GEMINI_API_KEY = (
    os.environ.get("GEMINI_API_KEY")  # Replace with your actual API key
)
HADITH_API_KEY = os.environ.get("HADITH_API_KEY")  # Replace with your actual API key
TRANSLATION_PROMPT = """
You are a highly skilled translator specializing in Islamic texts. Your task is to translate Hadith data from English to Malay (Malaysia), ensuring accuracy, cultural sensitivity, and preservation of the original message's religious and spiritual meaning.

**Instructions:**

1.  **Input:** You will receive Hadith data in JSON format, including fields such as `english_text`, `book_name`, `narrator`, `status`, and `hadith_number`.

2.  **Translation:** Translate all relevant text fields into accurate and fluent Malay (Malaysia).
    *   Preserve the religious and spiritual meaning of the Hadith.
    *   Maintain consistency in terminology.
    *   Use standard Malay spelling and grammar.

3.  **Technical Terms:** Retain technical Islamic terms (e.g., *Sahih*, *Hadith*, names of prophets and companions) in their original form if a direct, equivalent Malay term does not exist or if using the original term is culturally preferred and understood by Malay speakers.

4.  **Title Generation:** Create a brief, meaningful title in Malay (Malaysia) that accurately summarizes the essence of the Hadith.  This should be stored in the `tajuk_hadith` field.

5.  **Field Completion:** Translate the following english field to malay and use this key instead "narrator" should be "perawi_melayu","book_name" to "nama_buku","writerName" to "penulis_buku","status" to "status","hadith_number" to "hadith_number"

6.  **Output Format:** Return the translated data in JSON format, with the following structure(make sure to ensuring that the JSON is valid and parsable. Avoid unterminated strings, trailing commas, and invalid escape sequences that will cause a json decode error):

    {
        "id": ,
        "hadith_number": "",
        "status": "",
        "nama_buku": "",
        "penulis_buku": "",
        "tajuk_hadith": "",
        "perawi_melayu": "",
        "english_text": "",
        "malay_translation": ""
    }

7.  **Handling Missing Data:** If data is missing for some section, create a suitable one for it in malay. and if the data is not available in the english_text field, please use the arabic_text field for translation. and put "Not Available" in the english_text field.

8.  **Contextual Understanding:**  Demonstrate a deep understanding of Islamic context when translating. Consider cultural nuances and avoid literal translations that may distort the intended meaning.

9.  Warning: Islamic Unicode characters may included in Hadith data field. Please ensure proper handling.Ensure that your JSON output uses UTF-8 encoding to preserve non-ASCII characters like Arabic.
"""

BOOKS = {
    "Sahih Bukhari": "sahih-bukhari",
    "Sahih Muslim": "sahih-muslim",
    "Jami' Al-Tirmidhi": "al-tirmidhi",
    "Sunan Abu Dawood": "abu-dawood",
    "Sunan Ibn-e-Majah": "ibn-e-majah",
    "Sunan An-Nasa`i": "sunan-nasai",
    "Mishkat Al-Masabih": "mishkat",
    "Musnad Ahmad": "musnad-ahmad",
    "Al-Silsila Sahiha": "al-silsila-sahiha",
}


# Main execution
try:
    if __name__ == "__main__":
        try:
            # Create a main directory to store all hadiths
            os.makedirs("hadiths", exist_ok=True)

            error_hadith_numbers = []  # Initialize list to store error hadith numbers

            for book_name, book_slug in BOOKS.items():
                process_book(
                    book_slug,
                    book_name,
                    HADITH_API_KEY,
                    GEMINI_API_KEY,
                    TRANSLATION_PROMPT,
                    error_hadith_numbers,
                )

            print("All books processed.")

            # Save the error hadith numbers to a JSON file
            if error_hadith_numbers:
                with open("hadiths/error_hadiths.json", "w", encoding="utf-8") as f:
                    json.dump(error_hadith_numbers, f, indent=2, ensure_ascii=False)
                print(
                    f"Error Hadith Numbers saved to: hadiths/error_hadiths.json"
                )  # Inform user
            else:
                print("No Error Hadiths found.")

        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}")
            print("Running check_link_status.py to check network connection...")
            subprocess.run(
                [
                    "python",
                    "C:\\Users\\User\\OneDrive\\Downloads\\hadith\\check_link_status.py",
                ]
            )
            sys.exit(1)
        except requests.exceptions.RequestException as e:
            print(f"A network error occurred: {e}")
            print("Running check_link_status.py to check network connection...")
            subprocess.run(
                ["python", "C:\\Users\\User\\OneDrive\\Downloads\\hadith\\check_link_status.py"]
            )
            sys.exit(1)

except KeyboardInterrupt:
    print('Script stopped by user!')
    # Save the error hadith numbers to a JSON file
    if error_hadith_numbers:
        with open("hadiths/error_hadiths.json", "w", encoding="utf-8") as f:
            json.dump(error_hadith_numbers, f, indent=2, ensure_ascii=False)
        print(
            f"Error Hadith Numbers saved to: hadiths/error_hadiths.json"
        )  # Inform user
    else:
        print("No Error Hadiths found.")
    sys.exit(0)
