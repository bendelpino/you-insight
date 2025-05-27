#!/usr/bin/env python3
import os
import secrets
import base64

def generate_flask_secret_key(byte_length=24):
    """Generate a secure random key appropriate for Flask's secret_key."""
    # Generate random bytes
    random_bytes = secrets.token_bytes(byte_length)
    # Convert to base64 for easier storage in env files
    encoded_key = base64.urlsafe_b64encode(random_bytes).decode('utf-8')
    return encoded_key

if __name__ == "__main__":
    # Generate the key
    secret_key = generate_flask_secret_key()
    
    # Print the key
    print("\nGenerated Flask Secret Key:")
    print(f"{secret_key}")
    
    # Provide instructions for adding to .env file
    print("\nTo add this key to your .env file, add or update the following line:")
    print(f"FLASK_SECRET_KEY='{secret_key}'")
    
    # Check if .env file exists and offer to update it
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    
    if os.path.exists(env_path):
        response = input("\nWould you like to add/update this key in your .env file? (y/n): ")
        if response.lower() == 'y':
            # Read existing content
            with open(env_path, 'r') as f:
                env_content = f.read()
            
            # Check if FLASK_SECRET_KEY already exists
            if 'FLASK_SECRET_KEY=' in env_content:
                # Replace existing line
                lines = env_content.splitlines()
                updated_lines = []
                for line in lines:
                    if line.startswith('FLASK_SECRET_KEY='):
                        updated_lines.append(f"FLASK_SECRET_KEY='{secret_key}'")
                    else:
                        updated_lines.append(line)
                updated_content = '\n'.join(updated_lines)
            else:
                # Add new line
                if env_content and not env_content.endswith('\n'):
                    updated_content = env_content + f"\nFLASK_SECRET_KEY='{secret_key}'"
                else:
                    updated_content = env_content + f"FLASK_SECRET_KEY='{secret_key}'"
            
            # Write updated content
            with open(env_path, 'w') as f:
                f.write(updated_content)
            
            print("Your .env file has been updated with the new secret key.")
        else:
            print("No changes were made to your .env file.")
    else:
        print(f"\nNote: No .env file found at {env_path}")
        print("You can create it manually and add the secret key.")
