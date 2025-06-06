# services/send_email

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os

def send_email(
    sender_email: str,
    receiver_email: str,
    subject: str,
    message: str,
    attached_file: str = None,
    time: str = "now"  # Placeholder for future scheduling logic
) -> bool:
    """
    Centralized function to send an email via an external service (e.g., OVH).

    This function currently provides a mock implementation by printing email details.
    You will need to replace the 'MOCK: Simulating email sending...' section
    with the actual API call to your OVH automated email sending service.

    Args:
        sender_email (str): The email address of the sender.
        receiver_email (str): The email address of the recipient.
        subject (str): The subject line of the email.
        message (str): The body of the email.
        attached_file (str, optional): The path to a file to attach. Defaults to None.
        time (str, optional): A placeholder for future scheduling functionality.
                              Currently only "now" is effectively handled. Defaults to "now".

    Returns:
        bool: True if the email was successfully sent (or simulated), False otherwise.
    """
    print(f"--- Initiating email send at {time} ---")
    print(f"Sender: {sender_email}")
    print(f"Receiver: {receiver_email}")
    print(f"Subject: {subject}")
    print(f"Message Body:\n{message}\n")

    if attached_file:
        print(f"Attachment requested: {attached_file}")
        if not os.path.exists(attached_file):
            print(f"ERROR: Attached file '{attached_file}' not found. Email will be sent without it.")
            attached_file = None # Ensure we don't try to attach a non-existent file

    # --- MOCK: Simulating email sending (REPLACE THIS SECTION WITH OVH API CALL) ---
    try:
        # In a real scenario, you would make an API call to OVH here.
        # This might involve:
        # 1. Importing an OVH SDK or making an HTTP POST request to their API endpoint.
        # 2. Authenticating with OVH (e.g., API keys, OAuth).
        # 3. Constructing the email payload according to OVH's API documentation,
        #    including sender, receiver, subject, message, and handling attachments.
        # 4. Sending the request and handling the response.

        print("MOCK: Simulating email sending... (Replace this with actual OVH API integration)")

        # Example of how you might construct the email object for a generic SMTP server
        # This part is illustrative and might not be directly used with an API,
        # but shows how email content is typically formed.
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject
        msg.attach(MIMEText(message, 'plain'))

        if attached_file:
            try:
                part = MIMEBase('application', 'octet-stream')
                with open(attached_file, 'rb') as file:
                    part.set_payload(file.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition',
                                f"attachment; filename= {os.path.basename(attached_file)}")
                msg.attach(part)
                print(f"MOCK: Attached '{os.path.basename(attached_file)}' to the email.")
            except Exception as e:
                print(f"MOCK ERROR: Could not attach file {attached_file}: {e}")
                # Decide if you want to fail the send or proceed without attachment
                return False # Or True if you want to send without the attachment

        # This part below is for actual SMTP sending, NOT OVH API.
        # It's commented out as it's not the primary request, but useful for reference.
        # with smtplib.SMTP_SSL('smtp.your_ovh_server.com', 465) as smtp: # Replace with OVH SMTP details
        #     smtp.login('your_ovh_email_username', 'your_ovh_email_password') # Replace with OVH credentials
        #     smtp.send_message(msg)

        print("MOCK: Email simulated as sent successfully.")
        return True
    except Exception as e:
        print(f"MOCK ERROR: An error occurred during email simulation: {e}")
        return False

# --- Example Usage (for testing the function) ---
if __name__ == "__main__":
    # Create a dummy file for attachment testing
    dummy_file_path = "test_attachment.txt"
    with open(dummy_file_path, "w") as f:
        f.write("This is a test attachment file.")

    print("\n--- Test Case 1: Basic Email ---")
    success_basic = send_email(
        sender_email="no-reply@yourcompany.com",
        receiver_email="recipient@example.com",
        subject="Important Update: System Notification",
        message="Dear User,\n\nThis is an automated message from our system."
                "\n\nPlease do not reply to this email."
                "\n\nRegards,\nYour Team"
    )
    print(f"Basic email simulation result: {success_basic}\n")

    print("\n--- Test Case 2: Email with Attachment ---")
    success_attachment = send_email(
        sender_email="alerts@yourcompany.com",
        receiver_email="admin@example.com",
        subject="Daily Report: Sales Performance",
        message="Hello Admin,\n\nPlease find attached the daily sales report.",
        attached_file=dummy_file_path
    )
    print(f"Email with attachment simulation result: {success_attachment}\n")

    print("\n--- Test Case 3: Email with Non-existent Attachment ---")
    success_non_existent = send_email(
        sender_email="support@yourcompany.com",
        receiver_email="user@example.com",
        subject="Your Support Request #12345",
        message="Thank you for contacting support. We will get back to you shortly.",
        attached_file="non_existent_file.pdf"
    )
    print(f"Email with non-existent attachment simulation result: {success_non_existent}\n")

    # Clean up dummy file
    if os.path.exists(dummy_file_path):
        os.remove(dummy_file_path)
