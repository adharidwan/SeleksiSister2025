import requests
from pqcrypto.sign.sphincs_shake_256s_simple import generate_keypair, sign, verify
import base64
import os
from datetime import datetime
import pyotp
import time
import hashlib

# CONSTANTS - Update these with your actual credentials
USERNAME = "13523098"  # Your NIM
PASSWORD = "adha"      # Your second name
TOTP_SECRET = 'hutao'  # Your waifu/favorite character name (processed)
POW_PREFIX = "13523098:if:adha"  # Format: nim:jurusan:nama
URL = "http://104.214.186.131:8000"

def getMathQuestion():
    """Fetch math question from server"""
    ENDPOINT = URL + "/challenge-math"
    try:
        response = requests.get(ENDPOINT, auth=(USERNAME, PASSWORD), timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching math question: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Network error fetching math question: {e}")
        return None

def generate_totp_code(secret):
    """Generate TOTP code with proper base32 encoding"""
    try:
        cleaned_secret = ''.join(c for c in secret.lower() if c.isalnum())
        
        secret_b32 = base64.b32encode(cleaned_secret.encode('utf-8')).decode('ascii')
        secret_b32 = secret_b32.rstrip('=')  # Remove padding
        
        totp = pyotp.TOTP(secret_b32)
        code = totp.now()
        return str(code)
    except Exception as e:
        print(f"Error generating TOTP code: {e}")
        return None

def load_current_secret_key():
    """Load the current secret key from file"""
    keys_folder = "keys"
    current_secret_path = os.path.join(keys_folder, "current_secret_key.txt")
    
    if not os.path.exists(current_secret_path):
        print("No current secret key found. Please run 'Activate Account' or 'Update Key' first.")
        return None
    
    try:
        with open(current_secret_path, 'r') as f:
            secret_key_b64 = f.read().strip()
        return base64.b64decode(secret_key_b64)
    except Exception as e:
        print(f"Error loading secret key: {e}")
        return None

def load_current_public_key():
    """Load the current public key from file"""
    keys_folder = "keys"
    current_public_path = os.path.join(keys_folder, "current_public_key.txt")
    
    if not os.path.exists(current_public_path):
        print("No current public key found. Please run 'Activate Account' or 'Update Key' first.")
        return None
    
    try:
        with open(current_public_path, 'r') as f:
            public_key_b64 = f.read().strip()
        return base64.b64decode(public_key_b64)
    except Exception as e:
        print(f"Error loading public key: {e}")
        return None

def test_signature():
    """Test signature creation and verification with correct parameter order"""
    print("=== Testing SPHINCS+ Signature Functions ===")
    
    public_key, secret_key = generate_keypair()
    print(f"✓ Generated keypair")
    print(f"  Public key length: {len(public_key)} bytes")
    print(f"  Secret key length: {len(secret_key)} bytes")
    
    file_path = "/home/rid1/Kuliah/SeleksiSister/stage01/dummy.pdf"

    with open(file_path, 'rb') as f:
        test_data = f.read()
    if not test_data:
        print("Error: Test data file is empty or not found.")
        return
    
    print(f"✓ Test data: {test_data}")
    
    try:
        signature = sign(secret_key, test_data)
        print(f"✓ Created signature ({len(signature)} bytes)")
        
        is_valid = verify(public_key, test_data, signature)
        if is_valid:
            print("✅ Signature verification: PASSED")
        else:
            print("❌ Signature verification: FAILED")
                        
    except Exception as e:
        print(f"❌ Signature test failed: {e}")

def is_pdf_file(file_path):
    """Check if file is a valid PDF"""
    if not file_path.lower().endswith('.pdf'):
        return False
    
    try:
        with open(file_path, 'rb') as file:
            header = file.read(4)
            return header == b'%PDF'
    except Exception as e:
        print(f"Error checking PDF file: {e}")
        return False

def solve_math_question(question_text):
    """Solve math question with time constraint"""
    try:
        # Clean the question - remove everything after '||' if present
        cleaned_question = question_text.strip().split('||')[0]
        print(f"Solving: {cleaned_question}")
        
        # Evaluate the mathematical expression
        # WARNING: eval() can be dangerous, but it's required for this challenge
        start_time = time.time()
        result = eval(cleaned_question)
        solve_time = time.time() - start_time
        
        print(f"Answer: {result} (solved in {solve_time:.3f}s)")
        return int(result)
    except Exception as e:
        print(f"Error solving math question: {e}")
        return None

def submitA():
    """Submit Stage A with improved error handling"""
    ENDPOINT = URL + "/stage-a/submit"
    
    print("=== Stage A Submission ===")
    
    secret_key = load_current_secret_key()
    if not secret_key:
        return False
        
    public_key = load_current_public_key()
    if not public_key:
        return False

    # public_key, secret_key = generate_keypair()
    
    print("Enter the PDF file path to submit:")
    file_path = input().strip()
    
    if not file_path or not os.path.exists(file_path):
        print("Error: File not found or no path provided.")
        return False
    
    if not is_pdf_file(file_path):
        print("Error: Only PDF files are allowed.")
        return False
    
    try:
        with open(file_path, 'rb') as file:
            pdf_bytes = file.read()
        print(f"✓ PDF file loaded ({len(pdf_bytes)} bytes)")
    except Exception as e:
        print(f"Error reading PDF file: {e}")
        return False
    
    totp_code = generate_totp_code(TOTP_SECRET)
    if not totp_code:
        print("Failed to generate TOTP code")
        return False
    print(f"✓ TOTP code generated: {totp_code}")
    
    question = getMathQuestion()
    if not question:
        print("Failed to get math question")
        return False
    
    question_text = question['question']
    question_answer = solve_math_question(question_text)
    if question_answer is None:
        print("Failed to solve math question")
        return False
    
    signature = sign(secret_key, pdf_bytes)
    if not signature:
        print("Failed to create signature")
        return False
    print(f"✓ PDF signature created")
    
    is_valid = verify(public_key, pdf_bytes, signature)
    if not is_valid:
        print("❌ Signature verification failed")
        return False
    print("✓ Signature verification passed")
    print("Enter stage number (1 or 2):")
    try:
        tahap = int(input().strip())
        if tahap not in [1, 2]:
            print("Error: Stage must be 1 or 2")
            return False
    except ValueError:
        print("Error: Invalid stage number")
        return False

    print(f"\n=== Submitting Stage A (Tahap {tahap}) ===")
    print(f"File: {os.path.basename(file_path)}")
    print(f"Size: {len(pdf_bytes)} bytes")
    print(f"TOTP: {totp_code}")
    print(f"Math: {question_text} = {question_answer}")
    
    try:        
        files = {
        'file': ('document.pdf', pdf_bytes, 'application/pdf')
        }

        data = {
            'username': USERNAME,
            'totp_code': totp_code,
            'math_question': str(question_text),
            'math_answer': int(question_answer),
            'signature': base64.b64encode(signature).decode('utf-8'),
            'tahap': int(tahap)
        }

        response = requests.post(
            ENDPOINT,
            data=data,
            files=files,
            auth=(USERNAME, PASSWORD),
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Stage A submitted successfully!")
            return True
        else:
            print(f"❌ Submission failed: {response.status_code}")
            # print("Response:", response.text[::10])
            #write the response to a file
            try:
                # Save the response to a file
                with open("submission_response.txt", "w") as f:
                    f.write(response.text)
                print("Response saved to submission_response.txt")
            except Exception as e:
                print(f"Error saving response: {e}")
            print("Response:", response.text)
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error during submission: {e}")
        return False

def find_nonce_pow(pow_prefix, difficulty=5):
    """Find nonce for Proof of Work with progress reporting"""
    target = '0' * difficulty
    nonce = 0
    
    print(f"=== Proof of Work Mining ===")
    print(f"Prefix: {pow_prefix}")
    print(f"Target: hash must start with {target}")
    print(f"Difficulty: {difficulty}")
    
    start_time = time.time()
    
    while True:
        test_str = f"{pow_prefix}:{nonce}"
        hash_result = hashlib.sha256(test_str.encode()).hexdigest()
        
        if hash_result.startswith(target):
            elapsed = time.time() - start_time
            print(f"✅ Found nonce: {nonce}")
            print(f"   Hash: {hash_result}")
            print(f"   Time: {elapsed:.2f} seconds")
            print(f"   Rate: {nonce/elapsed:.0f} hashes/sec")
            return nonce
            
        nonce += 1
        if nonce % 50000 == 0:
            elapsed = time.time() - start_time
            rate = nonce / elapsed if elapsed > 0 else 0
            print(f"   Tried {nonce:,} nonces... ({rate:.0f} H/s)")

def activateAccount():
    """Activate account with PoW and key generation"""
    ENDPOINT = URL + "/activate-account"
    
    print("=== Account Activation ===")
    
    # Find nonce for Proof of Work
    nonce = find_nonce_pow(POW_PREFIX)
    
    # Generate SPHINCS+ keypair
    print("Generating SPHINCS+ keypair...")
    public_key, secret_key = generate_keypair()
    print(f"✓ Keypair generated")
    
    # Generate TOTP
    totp_code = generate_totp_code(TOTP_SECRET)
    if not totp_code:
        print("Failed to generate TOTP code")
        return False
    
    # Get and solve math question
    question = getMathQuestion()
    if not question:
        print("Failed to get math question")
        return False
    
    question_text = question['question']
    question_answer = solve_math_question(question_text)
    if question_answer is None:
        print("Failed to solve math question")
        return False
    
    # Prepare activation data
    data = {
        "username": USERNAME,
        "password": PASSWORD,
        "totp_code": totp_code,
        "math_question": question_text,
        "math_answer": question_answer,
        "nonce": nonce,
        "public_key": base64.b64encode(public_key).decode('utf-8')
    }
    
    print(f"Activating account...")
    try:
        response = requests.post(ENDPOINT, json=data, timeout=30)
        
        if response.status_code == 200:
            print("✅ Account activated successfully!")
            try:
                print("Response:", response.json())
            except:
                print("Response:", response.text)
            
            # Save keys
            save_keys_to_folder(public_key, secret_key)
            return True
        else:
            print(f"❌ Account activation failed: {response.status_code}")
            print("Response:", response.text)
            try:
                print("JSON:", response.json())
            except:
                pass
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error during activation: {e}")
        return False

def save_keys_to_folder(public_key, secret_key):
    """Save keys to files with timestamps"""
    keys_folder = "keys"
    if not os.path.exists(keys_folder):
        os.makedirs(keys_folder)
    
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    readable_timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # Save timestamped keys
    public_key_path = os.path.join(keys_folder, f"public_key_{timestamp}.txt")
    with open(public_key_path, 'w') as f:
        f.write(f"# SPHINCS+ Public Key\n")
        f.write(f"# Generated: {readable_timestamp}\n")
        f.write(f"# Timestamp: {timestamp}\n\n")
        f.write(base64.b64encode(public_key).decode('utf-8'))
    
    secret_key_path = os.path.join(keys_folder, f"secret_key_{timestamp}.txt")
    with open(secret_key_path, 'w') as f:
        f.write(f"# SPHINCS+ Secret Key\n")
        f.write(f"# Generated: {readable_timestamp}\n")
        f.write(f"# Timestamp: {timestamp}\n")
        f.write(f"# WARNING: Keep this secret!\n\n")
        f.write(base64.b64encode(secret_key).decode('utf-8'))
    
    # Save current keys
    current_public_path = os.path.join(keys_folder, "current_public_key.txt")
    current_secret_path = os.path.join(keys_folder, "current_secret_key.txt")
    
    with open(current_public_path, 'w') as f:
        f.write(base64.b64encode(public_key).decode('utf-8'))
    with open(current_secret_path, 'w') as f:
        f.write(base64.b64encode(secret_key).decode('utf-8'))
    
    print(f"✓ Keys saved to {keys_folder}/ folder")
    print(f"  Timestamped: {public_key_path}, {secret_key_path}")
    print(f"  Current: {current_public_path}, {current_secret_path}")

def updateKey():
    """Update public key on server"""
    ENDPOINT = URL + "/update-public-key"
    
    print("=== Key Update ===")
    
    # Generate new keypair
    public_key, secret_key = generate_keypair()
    print("✓ New keypair generated")
    
    # Generate TOTP
    totp_code = generate_totp_code(TOTP_SECRET)
    if not totp_code:
        print("Failed to generate TOTP code")
        return False
    
    # Get and solve math question
    question = getMathQuestion()
    if not question:
        print("Failed to get math question")
        return False
        
    question_text = question['question'] 
    question_answer = solve_math_question(question_text)
    if question_answer is None:
        print("Failed to solve math question")
        return False
    
    # Prepare update data
    data = {
        "username": USERNAME,
        "password": PASSWORD,
        "totp_code": totp_code,
        "math_question": question_text,
        "math_answer": question_answer,
        "new_public_key": base64.b64encode(public_key).decode('utf-8'),        
    }
    
    try:
        response = requests.post(ENDPOINT, json=data, auth=(USERNAME, PASSWORD), timeout=30)
        
        if response.status_code == 200:
            print("✅ Key updated successfully!")
            try:
                print("Response:", response.json())
            except:
                print("Response:", response.text)
            
            # Save new keys
            save_keys_to_folder(public_key, secret_key)
            return True
        else:
            print(f"❌ Key update failed: {response.status_code}")
            print("Response:", response.text)
            try:
                print("JSON:", response.json())
            except:
                pass
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error during key update: {e}")
        return False

def getSubmission():
    """Get submission status with TOTP authentication"""
    ENDPOINT = URL + f"/user/{USERNAME}/submissions"
    
    # Generate TOTP code (required parameter)
    totp_code = generate_totp_code(TOTP_SECRET)
    if not totp_code:
        print("Failed to generate TOTP code")
        return False
    
    try:
        # Add totp_code as query parameter
        params = {
            'totp_code': totp_code
        }
        
        response = requests.get(
            ENDPOINT, 
            params=params,
            auth=(USERNAME, PASSWORD), 
            timeout=10
        )
        
        if response.status_code == 200:
            print("=== Submissions ===")
            try:
                submissions = response.json()
                if isinstance(submissions, list):
                    if len(submissions) == 0:
                        print("No submissions found.")
                    else:
                        for i, sub in enumerate(submissions, 1):
                            print(f"{i}. {sub}")
                else:
                    print(submissions)
                return True
            except Exception as e:
                print(f"Error parsing JSON response: {e}")
                print("Raw response:", response.text)
                return False
        else:
            print(f"❌ Error getting submissions: {response.status_code}")
            print("Response:", response.text)
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error getting submissions: {e}")
        return False

def getStats():
    """Get user statistics"""
    ENDPOINT = URL + f"/stats"
    
    try:
        response = requests.get(ENDPOINT, auth=(USERNAME, PASSWORD), timeout=10)
        
        if response.status_code == 200:
            print("=== User Stats ===")
            try:
                print(response.json())
            except:
                print(response.text)
        else:
            print(f"Error getting stats: {response.status_code}")
            print("Response:", response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"Network error getting stats: {e}")

def debugSaveKeys():
    """Debug function to save keys without activation"""
    print("=== Debug: Save Keys ===")
    
    public_key, secret_key = generate_keypair()
    print("✓ Generated keypair")
    
    save_keys_to_folder(public_key, secret_key)
    print("Keys saved successfully for debugging purposes.")
    temp_public_key = load_current_public_key()
    temp_secret_key = load_current_secret_key()
    if public_key == temp_public_key and secret_key == temp_secret_key:
        print("Debug: Keys loaded successfully from current files.")
    else:
        print("Debug: Keys do not match current files, check your save logic.")

def main():
    """Main menu loop"""
    print("=== Lab Sister Submission System ===")
    print("Make sure to update the constants at the top of the script with your credentials!")
    print(f"Current Username: {USERNAME}")
    print(f"Current Password: {PASSWORD}")
    print(f"Current TOTP Secret: {TOTP_SECRET}")
    print(f"Current POW Prefix: {POW_PREFIX}")
    
    while True:
        print("\n" + "="*50)
        print("1: Submit Stage A")
        print("2: Submit Stage B (Not implemented)")
        print("3: Update Key")
        print("4: Get Submissions")
        print("5: Activate Account")
        print("6: Get Stats")
        print("7: Get Math Question (Test)")
        print("8: Test TOTP Generation")
        print("9: Test Signature Functions")
        print("0: Exit")
        print("Choose option: ", end="")
        
        try:
            choice = input().strip()
            if not choice:
                continue
                
            choice = int(choice)
        except ValueError:
            print("Invalid input. Please enter a number.")
            continue

        if choice == 1:
            submitA()
        elif choice == 2:
            print("Submit B not implemented yet")
        elif choice == 3:
            updateKey()
        elif choice == 4:
            getSubmission()
        elif choice == 5:
            activateAccount()
        elif choice == 6:
            getStats()
        elif choice == 7:
            question = getMathQuestion()
            if question:
                print("Math Question:", question)
                answer = solve_math_question(question['question'])
                print(f"Calculated Answer: {answer}")
        elif choice == 8:
            totp_code = generate_totp_code(TOTP_SECRET)
            print(f"Generated TOTP code: {totp_code}")
        elif choice == 9:
            test_signature()
        elif choice == 10:
            debugSaveKeys()
        elif choice == 0:
            print("Goodbye!")
            break
        else:
            print("Invalid choice, please try again.")

if __name__ == "__main__":
    main()