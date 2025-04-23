import os
from openai import OpenAI
import base64
from dotenv import load_dotenv
import requests
from urllib.parse import urlparse
import io
import pyheif
from PIL import Image
import psycopg2
import sys

load_dotenv()

OPENAI_KEY = os.environ.get('OPENAI_KEY')
DB_NAME = os.environ.get('DB_NAME', 'instagram')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'postgres')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')

SUPPORTED_FORMATS = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']

BATCH_PROMPT_TEMPLATE = """
# BATCH PROMPT TEMPLATE
# You can define how to refine or add to the interests based on new following list data and previous results.
# The variables available:
# - previous_response (from the last LLM output)
# - current_following_batch (subset of following list)
# Example:
# Based on the previous result:
{previous_response}

Now here is a new batch of people/brands/pages this person follows:
{current_following_batch}

Please refine or expand the list of interests accordingly.
Return the updated list of interests like:
["interest1", "interest2", "interest3"]
"""

def connect_to_db():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {str(e)}")
        return None

def get_user_data(username):
    conn = connect_to_db()
    if not conn:
        return None, None, None

    try:
        cur = conn.cursor()
        cur.execute("SELECT pk FROM user_data WHERE username = %s", (username,))
        user_pk_result = cur.fetchone()

        if not user_pk_result:
            print(f"User '{username}' not found in the database")
            return None, None, None

        user_pk = user_pk_result[0]
        cur.execute("SELECT post_urls, captions, following_list FROM user_detail WHERE pk = %s", (user_pk,))
        result = cur.fetchone()

        if not result:
            print(f"No details found for user '{username}'")
            return None, None, None

        post_urls = result[0] if result[0] else []
        captions = result[1] if result[1] else []
        following_list = result[2] if result[2] else []

        return post_urls, captions, following_list

    except Exception as e:
        print(f"Error querying database: {str(e)}")
        return None, None, None
    finally:
        if conn:
            conn.close()

def instagram_image_to_base64(url):
    try:
        parsed_url = urlparse(url)
        if not parsed_url.netloc or not parsed_url.scheme:
            return {"error": "Invalid URL format"}

        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        response = requests.get(url, headers=headers, stream=True)
        if response.status_code != 200:
            return {"error": f"Failed to fetch image: HTTP {response.status_code}"}

        content_type = response.headers.get('Content-Type', '').lower()
        image_data = response.content

        if 'heic' in content_type or url.endswith('.heic'):
            try:
                heif_file = pyheif.read_heif(image_data)
                image = Image.frombytes(
                    heif_file.mode,
                    heif_file.size,
                    heif_file.data,
                    "raw",
                    heif_file.mode,
                    heif_file.stride,
                )
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG")
                image_data = buffer.getvalue()
                content_type = 'image/jpeg'
                print("Successfully converted HEIC to JPEG")
            except Exception as e:
                return {"error": f"Failed to convert HEIC: {str(e)}"}

        elif content_type not in SUPPORTED_FORMATS:
            return {"error": f"Unsupported image format: {content_type}"}

        try:
            Image.open(io.BytesIO(image_data)).verify()
        except Exception:
            return {"error": "Image data is corrupt or invalid"}

        base64_data = base64.b64encode(image_data).decode('utf-8')
        return {
            "data_uri": f"data:{content_type};base64,{base64_data}",
            "base64_data": base64_data,
            "content_type": content_type
        }

    except Exception as e:
        return {"error": f"Error processing image: {str(e)}"}

def create_content_list(img_urls, captions=None):
    if captions is None:
        captions = [None] * len(img_urls)

    content_list = []
    for url, caption in zip(img_urls, captions):
        result = instagram_image_to_base64(url)
        if isinstance(result, dict) and "error" in result:
            print(f"Error processing {url}: {result['error']}")
            continue

        content_list.append({
            "type": "image_url",
            "image_url": {"url": result["data_uri"]}
        })

        if caption:
            content_list.append({
                "type": "text",
                "text": caption
            })

    return content_list

def batch_list(lst, batch_size=20):
    for i in range(0, len(lst), batch_size):
        yield lst[i:i + batch_size]

def call_llm(client, content_list):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": content_list
        }]
    )
    return response.choices[0].message.content

def append_output_to_file(output, file_path="llm_outputs.txt"):
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(output)
        f.write("\n" + "="*80 + "\n")

def main():
    if len(sys.argv) != 2:
        print("Usage: python interest.py <username>")
        sys.exit(1)

    try:
        batch_size = int(input("Enter the batch size for following list (default is 20): ") or 20)
    except ValueError:
        print("Invalid input. Using default batch size of 20.")
        batch_size = 20
        
    username = sys.argv[1]
    img_urls, captions, following_list = get_user_data(username)

    if not img_urls or not captions:
        print(f"Could not retrieve data for username '{username}'")
        sys.exit(1)

    client = OpenAI(api_key=OPENAI_KEY)

    # First Call: Captions + Images
    initial_prompt = """
You are given some data about a person's social media. Based on that you have to predict the interests, hobbies or likings of the person.
The data is as follows:
Posts and Captions: You can get hashtags or keywords from captions and analyse images to get interests.
Don't be hasty about deciding interests observe if there are any trends.

Return a list of the interests of the person like so:
["interest1", "interest2", "interest3"]
"""

    content_list = [{"type": "text", "text": initial_prompt}]
    content_list += create_content_list(img_urls, captions)
    previous_response = call_llm(client, content_list)
    print("Initial Response:", previous_response)
    append_output_to_file(previous_response)

    # Follow-up Calls: Batching Following List
    for batch in batch_list(following_list, batch_size=batch_size):
        prompt = BATCH_PROMPT_TEMPLATE.format(
            previous_response=previous_response,
            current_following_batch="\n".join(batch)
        )
        content = [{"type": "text", "text": prompt}]
        previous_response = call_llm(client, content)
        print("Refined Response:", previous_response)
        append_output_to_file(previous_response)

if __name__ == "__main__":
    main()
