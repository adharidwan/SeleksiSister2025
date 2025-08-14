#!/usr/bin/env python3
import socket
import requests
import subprocess
import struct
import random
import time

def test_basic_connectivity():
    """Test basic network connectivity"""
    print("=== Basic Network Connectivity Tests ===")

    # Test if we can reach the DNS server
    dns_server = "169.254.123.252"
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        sock.connect((dns_server, 53))
        sock.close()
        print(f"✓ Can reach DNS server {dns_server}:53")
        return True
    except Exception as e:
        print(f"✗ Cannot reach DNS server {dns_server}:53 - {e}")
        return False

def dns_query_raw(domain, dns_server, query_type=1):
    """
    Send raw DNS query using UDP socket
    query_type: 1 = A record, 28 = AAAA record
    """
    try:
        print(f"Sending raw DNS query for {domain} to {dns_server}")

        # Create DNS query packet
        transaction_id = random.randint(0, 65535)

        # DNS Header (12 bytes)
        flags = 0x0100  # Standard query, recursion desired
        questions = 1
        answer_rrs = 0
        authority_rrs = 0
        additional_rrs = 0

        header = struct.pack('!HHHHHH',
                           transaction_id, flags, questions,
                           answer_rrs, authority_rrs, additional_rrs)

        # DNS Question
        question = b''
        for part in domain.split('.'):
            if part:  # Skip empty parts
                question += struct.pack('!B', len(part)) + part.encode()
        question += b'\x00'  # End of domain name
        question += struct.pack('!HH', query_type, 1)  # Type A, Class IN

        # Complete DNS packet
        dns_packet = header + question

        print(f"DNS packet size: {len(dns_packet)} bytes")
        print(f"Transaction ID: {transaction_id}")

        # Send DNS query
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(10)  # Increase timeout

        print(f"Sending query to {dns_server}:53...")
        sock.sendto(dns_packet, (dns_server, 53))

        # Receive response
        print("Waiting for response...")
        response, addr = sock.recvfrom(512)
        sock.close()

        print(f"Received response from {addr}: {len(response)} bytes")

        # Parse response (simplified)
        if len(response) < 12:
            print("Response too short")
            return None

        # Parse header
        resp_id, resp_flags, resp_questions, resp_answers = struct.unpack('!HHHH', response[:8])
        print(f"Response ID: {resp_id}, Flags: {hex(resp_flags)}, Answers: {resp_answers}")

        if resp_id != transaction_id:
            print(f"Transaction ID mismatch: sent {transaction_id}, got {resp_id}")
            return None

        if resp_answers == 0:
            print("No answers in response")
            return None

        # Skip header and question sections
        offset = 12

        # Skip question section
        while offset < len(response) and response[offset] != 0:
            length = response[offset]
            if length > 63:  # Compression pointer
                offset += 1
                break
            offset += length + 1
        offset += 5  # Skip null terminator and QTYPE/QCLASS
        # Parse answer section
        answers = []

        for i in range(resp_answers):
            if offset >= len(response) - 10:
                break

            # Skip name (compressed format)
            if response[offset] & 0xC0:
                offset += 2
            else:
                while offset < len(response) and response[offset] != 0:
                    length = response[offset]
                    if length > 63:  # Compression
                        offset += 1
                        break
                    offset += length + 1
                if offset < len(response) and response[offset] == 0:
                    offset += 1

            # Read type, class, ttl, length
            if offset + 10 > len(response):
                break

            rtype, rclass, ttl, rdlength = struct.unpack('!HHIH', response[offset:offset+10])
            offset += 10

            print(f"Answer {i+1}: Type={rtype}, Class={rclass}, TTL={ttl}, Length={rdlength}")

            if rtype == 1 and rdlength == 4:  # A record
                ip_bytes = response[offset:offset+4]
                ip = '.'.join(str(b) for b in ip_bytes)
                answers.append(ip)
                print(f"Found A record: {ip}")

            offset += rdlength

        return answers[0] if answers else None

    except socket.timeout:
        print("DNS query timed out")
        return None
    except Exception as e:
        print(f"Raw DNS query failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def dns_query_dig(domain, dns_server):
    """Use dig command for DNS resolution"""
    try:
        print(f"Using dig to query {domain} from {dns_server}")
        cmd = ['dig', f'@{dns_server}', domain, 'A', '+short', '+time=10']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

        print(f"dig command: {' '.join(cmd)}")
        print(f"dig return code: {result.returncode}")
        print(f"dig stdout: {result.stdout}")
        print(f"dig stderr: {result.stderr}")

        if result.returncode == 0 and result.stdout.strip():
            # Get the first IP from the output
            lines = result.stdout.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith(';') and '.' in line:
                    # Validate IP format
                    parts = line.split('.')
                    if len(parts) == 4:
                        try:
                            if all(0 <= int(part) <= 255 for part in parts):
                                return line
                        except ValueError:
                            continue
            return None
        else:
            print(f"dig command failed: {result.stderr}")
            return None

    except subprocess.TimeoutExpired:
        print("dig command timed out")
        return None
    except FileNotFoundError:
        print("dig command not found - please install dnsutils")
        return None
    except Exception as e:
        print(f"dig query failed: {e}")
        return None

def dns_query_nslookup(domain, dns_server):
    """Use nslookup command for DNS resolution"""
    try:
        print(f"Using nslookup to query {domain} from {dns_server}")
        cmd = ['nslookup', domain, dns_server]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

        print(f"nslookup command: {' '.join(cmd)}")
        print(f"nslookup return code: {result.returncode}")
        print(f"nslookup stdout: {result.stdout}")
        print(f"nslookup stderr: {result.stderr}")

        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if 'Address:' in line and dns_server not in line:
                    ip = line.split('Address:')[1].strip()
                    # Validate IP format
                    parts = ip.split('.')
                    if len(parts) == 4:
                        try:
                            if all(0 <= int(part) <= 255 for part in parts):
                                return ip
                        except ValueError:
                            continue

        print(f"nslookup failed: {result.stderr}")
        return None

    except Exception as e:
        print(f"nslookup query failed: {e}")
        return None

def resolve_dns_custom(domain, dns_server):
    """Try multiple methods to resolve DNS"""
    print(f"\n=== Resolving {domain} using DNS server {dns_server} ===")

    # Method 1: Try dig command
    print("\n--- Method 1: dig command ---")
    ip = dns_query_dig(domain, dns_server)
    if ip:
        print(f"✓ dig resolved: {domain} -> {ip}")
        return ip

    # Method 2: Try nslookup command
    print("\n--- Method 2: nslookup command ---")
    ip = dns_query_nslookup(domain, dns_server)
    if ip:
        print(f"✓ nslookup resolved: {domain} -> {ip}")
        return ip

    # Method 3: Try raw DNS query
    print("\n--- Method 3: raw DNS query ---")
    ip = dns_query_raw(domain, dns_server)
    if ip:
        print(f"✓ raw query resolved: {domain} -> {ip}")
        return ip

    print("\n✗ All DNS resolution methods failed")
    return None

def test_dns_server_connectivity(dns_server):
    """Test if DNS server is reachable"""
    print(f"\n=== Testing DNS Server Connectivity ===")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        sock.connect((dns_server, 53))
        sock.close()
        print(f"✓ DNS server {dns_server}:53 is reachable")
        return True
    except Exception as e:
        print(f"✗ DNS server {dns_server}:53 is not reachable: {e}")
        return False

def test_http_connection(domain, port, ip=None):
    """Test HTTP connection to the resolved IP"""
    if not ip:
        print(f"No IP provided for {domain}")
        return False

    print(f"\n=== Testing HTTP Connection ===")

    # Test basic socket connection first
    print(f"Testing socket connection to {ip}:{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((ip, port))
        sock.close()

        if result == 0:
            print(f"✓ Socket connection to {ip}:{port} successful")
        else:
            print(f"✗ Socket connection to {ip}:{port} failed (error {result})")
            return False
    except Exception as e:
        print(f"✗ Socket connection failed: {e}")
        return False

    # Test HTTP request
    try:
        print(f"Making HTTP request to http://{domain}:{port}...")

        # Use the resolved IP but keep the domain in Host header
        url = f"http://{ip}:{port}"
        headers = {'Host': domain}

        response = requests.get(url, headers=headers, timeout=10)

        print(f"✅ HTTP connection successful!")
        print(f"Status Code: {response.status_code}")
        print(f"Content-Length: {len(response.text)} chars")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response preview: {response.text[:200]}...")

        return True

    except requests.exceptions.ConnectionError as e:
        print(f"✗ HTTP connection failed: {e}")
        return False
    except Exception as e:
        print(f"✗ HTTP request failed: {e}")
        return False

def main():
    print("=== Enhanced DNS Client (web.deeznutts.local) ===\n")

    # Default settings
    domain = "web.deeznutts.local"
    port = 8080
    dns_server = "169.254.123.252"

    print("Choose option:")
    print("1. Test web.deeznutts.local:8080 with custom DNS")
    print("2. Test with different domain")
    print("3. Debug DNS server connectivity only")

    choice = input("\nEnter choice (1/2/3): ").strip()

    if choice == "2":
        domain = input("Enter domain: ").strip()
        port = int(input("Enter port: ").strip())
        dns_server = input("Enter DNS server (default: 169.254.123.252): ").strip() or "169.254.123.252"
    elif choice == "3":
        # Only test DNS connectivity
        print(f"\n{'='*60}")
        print(f"Testing DNS Server: {dns_server}")
        print(f"{'='*60}")

        if test_dns_server_connectivity(dns_server):
            print("\n--- Testing with a simple query ---")
            test_ip = dns_query_raw("test.local", dns_server)
            if test_ip:
                print(f"DNS server is responding: got {test_ip}")
            else:
                print("DNS server is reachable but not responding to queries")
        return

    print(f"\n{'='*60}")
    print(f"Testing: {domain}:{port}")
    print(f"DNS Server: {dns_server}")
    print(f"{'='*60}")

    # Test DNS server connectivity first
    if not test_dns_server_connectivity(dns_server):
        print("\n❌ Cannot reach DNS server. Check your network configuration.")
        return

    # Try to resolve the domain
    ip = resolve_dns_custom(domain, dns_server)

    if not ip:
        print(f"\n❌ Failed to resolve {domain}")
        print("\nTroubleshooting tips:")
        print("1. Check if bind9 is running on VM1:")
        print("   sudo systemctl status bind9")
        print("2. Check bind9 configuration:")
        print("   sudo named-checkconf")
        print("3. Check zone file:")
        print("   sudo named-checkzone deeznutts.local /etc/bind/db.deeznutts.local")
        print("4. Check if DNS server is listening:")
        print("   sudo netstat -tulpn | grep :53")
        print("5. Check bind9 logs:")
        print("   sudo journalctl -u bind9 -f")
        return

    # Test HTTP connection
    success = test_http_connection(domain, port, ip)

    if not success:
        print(f"\n❌ HTTP connection failed")
        print("\nTroubleshooting tips:")
        print("1. Check if the web server is running on VM2")
        print("2. Check if reverse proxy is running on VM4")
        print("3. Verify firewall settings")
        print(f"4. Try manual connection: telnet {ip} {port}")
    else:
        print(f"\n✅ Complete success! {domain} resolved to {ip} and HTTP connection works!")

if __name__ == "__main__":
    main()