import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def send_reset_email(email, reset_url):
    """
    Send a password reset email to the user
    
    Args:
        email (str): Recipient's email address
        reset_url (str): URL for password reset
    """
    # Get email configuration from environment variables
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    
    # Try to get SMTP port, handle invalid values
    smtp_port_str = os.getenv('SMTP_PORT', '587')
    try:
        smtp_port = int(smtp_port_str)
    except ValueError:
        # Use default port if the value is not a valid integer
        smtp_port = 587
        
    smtp_username = os.getenv('SMTP_USERNAME')
    smtp_password = os.getenv('SMTP_PASSWORD')
    sender_email = os.getenv('SENDER_EMAIL', smtp_username)
    
    # Check if we have valid SMTP credentials or just placeholder values
    placeholder_values = ['your_email_username', 'your_smtp_username', 'your_email_password', 'your_smtp_password']
    is_dev_mode = not all([smtp_username, smtp_password]) or smtp_username in placeholder_values or smtp_password in placeholder_values
    
    if is_dev_mode:
        # For development/testing without actual email sending
        print(f"[DEV MODE] Password reset link for {email}: {reset_url}")
        return True
    
    # Create message
    message = MIMEMultipart("alternative")
    message["Subject"] = "YouInsight - Password Reset"
    message["From"] = sender_email
    message["To"] = email
    
    # Create HTML email content
    html = f"""
    <html>
      <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
          <h2 style="color: #536DFE;">YouInsight Password Reset</h2>
          <p>We received a request to reset your password. If you made this request, click the button below to create a new password. This link will expire in 1 hour.</p>
          <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}" style="background-color: #536DFE; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold;">Reset Password</a>
          </div>
          <p>If you did not request a password reset, please ignore this email and your password will remain unchanged.</p>
          <hr style="border: 1px solid #eee; margin: 30px 0;">
          <p style="color: #777; font-size: 12px;">This is an automated email, please do not reply.</p>
        </div>
      </body>
    </html>
    """
    
    # Add HTML part to message
    part = MIMEText(html, "html")
    message.attach(part)
    
    try:
        # Connect to mail server
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(sender_email, email, message.as_string())
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
