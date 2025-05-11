import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import date

# Get environment variables
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
RECIPIENTS = os.getenv("RECIPIENTS").split(",")

def send_email_with_png():
    # Create message
    msg = MIMEMultipart("related")
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = ", ".join(RECIPIENTS)
    
    # Set subject with today's date
    today = date.today().strftime("%B %d, %Y")
    subject = f"Tamil Word/Phrase of the Day – {today}"
    msg["Subject"] = subject

    # HTML body with only the image embedded
    html = '<html><body><img src="cid:image1"></body></html>'
    msg.attach(MIMEText(html, "html"))

    # Attach the PNG image
    with open("output_phrase.png", "rb") as img:
        img_data = img.read()
        image = MIMEImage(img_data, name="output_phrase.png")
        image.add_header("Content-ID", "<image1>")
        image.add_header("Content-Disposition", "inline", filename="output_phrase.png")
        msg.attach(image)

    # Send email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, RECIPIENTS, msg.as_string())
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {str(e)}")

if __name__ == "__main__":
    send_email_with_png() 