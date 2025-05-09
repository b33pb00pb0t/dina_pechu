import openai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import date

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
RECIPIENTS = os.getenv("RECIPIENTS").split(",")

PHRASES_FILE = "phrases.txt"

def get_used_words():
    if not os.path.exists(PHRASES_FILE):
        return set()
    with open(PHRASES_FILE, "r") as file:
        return set(line.strip().lower() for line in file.readlines())

def save_word(word):
    with open(PHRASES_FILE, "a") as file:
        file.write(word + "\n")

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
            # Fallback to static file
            return get_next_static_phrase()

        # Try to extract the word from the response
        for line in output.splitlines():
            if line.lower().startswith("word:"):
                word = line.split(":", 1)[1].strip().lower()
                if word not in used_words:
                    save_word(word)
                    return output
        attempt += 1
    # If OpenAI fails to provide a new word, fallback to static file
    return get_next_static_phrase()

def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = ", ".join(RECIPIENTS)
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, RECIPIENTS, msg.as_string())

def get_next_static_phrase():
    if not os.path.exists("static_phrases.txt"):
        return "No static phrases file found."
    used_words = get_used_words()
    with open("static_phrases.txt", "r", encoding="utf-8") as f:
        content = f.read()
    phrases = [p.strip() for p in content.split("\n\n") if p.strip()]
    for phrase in phrases:
        # Extract the word line
        for line in phrase.splitlines():
            if line.lower().startswith("word:"):
                word = line.split(":", 1)[1].strip().lower()
                if word not in used_words:
                    save_word(word)
                    return phrase
    return "No unused static phrases left."

def main():
    phrase = get_unique_tamil_phrase()
    today = date.today().strftime("%B %d, %Y")
    subject = f"Tamil Word/Phrase of the Day – {today}"
    send_email(subject, phrase)
    print("✅ Phrase sent!")

if __name__ == "__main__":
    main()
