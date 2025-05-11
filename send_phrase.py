import openai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
import os
from datetime import date
import re
from lxml import etree
import cairosvg
import requests
import base64
from io import BytesIO

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
RECIPIENTS = os.getenv("RECIPIENTS").split(",")

PHRASES_FILE = "phrases.txt"
TEMPLATE_SVG = "dina_pechu_template.svg"
OUTPUT_SVG = "filled_phrase.svg"
OUTPUT_PNG = "output_phrase.png"
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

def get_used_words():
    if not os.path.exists(PHRASES_FILE):
        return set()
    with open(PHRASES_FILE, "r", encoding="utf-8") as file:
        return set(line.strip().lower() for line in file.readlines())

def save_word(word):
    with open(PHRASES_FILE, "a", encoding="utf-8") as file:
        file.write(word + "\n")

def parse_phrase_output(text):
    fields = {
        "word": "",
        "transliteration": "",
        "translation": "",
        "meaning": "",
        "pronunciation": "",
        "example_sentence": "",
        "example_sentence_transliteration": "",
        "example_sentence_translation": ""
    }
    for line in text.splitlines():
        if ':' in line:
            label, value = line.split(':', 1)
            key = label.strip().lower()
            value = value.strip()
            if key.startswith("word"):
                fields["word"] = value
            elif key.startswith("transliteration") and not key.startswith("example_sentence_transliteration"):
                fields["transliteration"] = value
            elif key.startswith("meaning") or key.startswith("translation"):
                fields["translation"] = value
                fields["meaning"] = value
            elif key.startswith("pronunciation"):
                fields["pronunciation"] = value
            elif key == "example_sentence":
                fields["example_sentence"] = value
            elif key == "example_sentence_transliteration":
                fields["example_sentence_transliteration"] = value
            elif key == "example_sentence_translation":
                fields["example_sentence_translation"] = value
    return fields

def get_unique_tamil_phrase():
    used_words = get_used_words()
    attempt = 0
    while attempt < 5:
        prompt = (
            "Give me 1 Tamil word or phrase (commonly used) that is helpful for learning Tamil. "
            "with: 1) the word, 2) transliteration, 3) English meaning, "
            "4) a basic Tamil sentence using it, and 5) its English transliteration + translation. "
            "Return it in clear labeled format.."
        )
        try:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            output = response.choices[0].message.content.strip()
        except Exception as e:
            return get_next_static_phrase(return_structured=True)
        for line in output.splitlines():
            if line.lower().startswith("word:"):
                word = line.split(":", 1)[1].strip().lower()
                if word not in used_words:
                    save_word(word)
                    return parse_phrase_output(output)
        attempt += 1
    return get_next_static_phrase(return_structured=True)

def get_next_static_phrase(return_structured=False):
    static_file = "static_phrases.txt"
    if not os.path.exists(static_file):
        return {} if return_structured else "No static phrases file found."
    used_words = get_used_words()
    with open(static_file, "r", encoding="utf-8") as f:
        content = f.read()
    blocks = [block.strip() for block in content.split('---') if block.strip()]
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        phrase_dict = {}
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                phrase_dict[key.strip().lower()] = value.strip()
        word = phrase_dict.get('word', '').lower()
        if word and word not in used_words:
            save_word(word)
            if return_structured:
                block_text = '\n'.join(f"{k}: {v}" for k, v in phrase_dict.items())
                return parse_phrase_output(block_text)
            else:
                return '\n'.join(f"{k}: {v}" for k, v in phrase_dict.items())
    return {} if return_structured else "No unused static phrases left."

def get_unsplash_image_url(query):
    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": query,
        "client_id": UNSPLASH_ACCESS_KEY,
        "per_page": 1,
        "orientation": "landscape"
    }
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        return None
    data = resp.json()
    if "results" in data and len(data["results"]) > 0:
        img_url = data["results"][0]["urls"]["regular"]
        return img_url
    else:
        return None

def get_image_data_uri(url):
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            img_bytes = BytesIO(resp.content)
            img_base64 = base64.b64encode(img_bytes.read()).decode('utf-8')
            ext = url.split('.')[-1].lower()
            if ext not in ['jpg', 'jpeg', 'png', 'gif']:
                ext = 'jpeg'
            data_uri = f"data:image/{ext};base64,{img_base64}"
            return data_uri
        else:
            return None
    except Exception as e:
        return None
    return None

def fill_svg_and_convert(data, template_path=TEMPLATE_SVG, output_svg=OUTPUT_SVG, output_png=OUTPUT_PNG):
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(template_path, parser)
    root = tree.getroot()
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    meaning = data.get("meaning", data.get("translation", ""))
    image_url = get_unsplash_image_url(meaning)
    image_data_uri = get_image_data_uri(image_url) if image_url else None
    if image_data_uri:
        image_elem = root.xpath("//svg:image[@id='image_meaning']", namespaces=ns)
        if image_elem:
            image_elem[0].set("{http://www.w3.org/1999/xlink}href", image_data_uri)
            image_elem[0].set("href", image_data_uri)
    id_map = {
        "date": data.get("date", ""),
        "word": data.get("word", ""),
        "trans_meaning_pron": f"{data.get('transliteration', '')} - {meaning} - {data.get('pronunciation', '')}",
        "example_sentence": f"Example sentence in Tamil: {data.get('example_sentence', '')}",
        "example_sentence_transliteration": f"Transliteration of the example: {data.get('example_sentence_transliteration', '')}",
        "example_sentence_translation": f"Translation of example: {data.get('example_sentence_translation', '')}"
    }
    for key, value in id_map.items():
        elements = root.xpath(f"//svg:text[@id='{key}']", namespaces=ns)
        if elements:
            elements[0].text = value
        tspan_elements = root.xpath(f"//svg:tspan[@id='{key}']", namespaces=ns)
        if tspan_elements:
            tspan_elements[0].text = value
    tree.write(output_svg, pretty_print=True)
    # PNG will be generated by rsvg-convert in the workflow
    return output_png

def send_email(subject, image_path):
    msg = MIMEMultipart("related")
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = ", ".join(RECIPIENTS)
    msg["Subject"] = subject

    # HTML body with only the image embedded
    html = '<html><body><img src="cid:image1"></body></html>'
    msg.attach(MIMEText(html, "html"))

    # Attach the image
    with open(image_path, "rb") as img:
        img_data = img.read()
        image = MIMEImage(img_data, name=os.path.basename(image_path))
        image.add_header("Content-ID", "<image1>")
        image.add_header("Content-Disposition", "inline", filename=os.path.basename(image_path))
        msg.attach(image)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, RECIPIENTS, msg.as_string())

def main():
    phrase_data = get_unique_tamil_phrase()
    today = date.today().strftime("%B %d, %Y")
    phrase_data["date"] = today
    fill_svg_and_convert(phrase_data)

if __name__ == "__main__":
    main()
