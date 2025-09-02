import socket
import threading
import re
import subprocess
import os
import netifaces
import time

class ReverseProxy:
    def __init__(self):
        self.proxy_host = "0.0.0.0"  # Listen on all interfaces
        self.proxy_port = 8080  # Match client.py's port
        self.target_host = "169.254.187.117"  # VM2's IP (confirm this matches)
        self.target_port = 8080  # VM2's HTTP server port

        # Auto-detect current IP for logging
        self.current_ip = self.get_current_ip()
        print(f"Reverse Proxy running on: {self.current_ip}")

        # Test connection to backend server first
        if self.test_backend_connection():
            print(f"✓ Backend server {self.target_host}:{self.target_port} is reachable")
        else:
            print(f"⚠ WARNING: Backend server {self.target_host}:{self.target_port} may not be reachable")
            print("Make sure VM2 is running and serving HTTP on port 8080")

        # Set up firewall
        self.setup_firewall()

        # Start the proxy server
        self.start()

    def get_current_ip(self):
        """Auto-detect current IP address"""
        try:
            interfaces = netifaces.interfaces()
            for interface in interfaces:
                if interface == 'lo':
                    continue
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr['addr']
                        if not ip.startswith('127.'):
                            return ip
        except Exception as e:
            print(f"Error detecting IP: {e}")
        return "unknown"

    def test_backend_connection(self):
        """Test if backend server is reachable"""
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(3)
            result = test_socket.connect_ex((self.target_host, self.target_port))
            test_socket.close()
            return result == 0
        except Exception as e:
            print(f"Backend connection test failed: {e}")
            return False

    def setup_firewall(self):
        """Setup iptables firewall rules for bonus points"""
        print("Setting up firewall rules...")
        try:
            # Clear existing rules (be careful in production!)
            subprocess.run(["sudo", "iptables", "-F"], check=False)
            subprocess.run(["sudo", "iptables", "-X"], check=False)

            # Set default policies
            subprocess.run(["sudo", "iptables", "-P", "INPUT", "ACCEPT"], check=False)
            subprocess.run(["sudo", "iptables", "-P", "FORWARD", "ACCEPT"], check=False)
            subprocess.run(["sudo", "iptables", "-P", "OUTPUT", "ACCEPT"], check=False)

            # Allow loopback
            subprocess.run(["sudo", "iptables", "-A", "INPUT", "-i", "lo", "-j", "ACCEPT"], check=False)

            # Allow established connections
            subprocess.run(["sudo", "iptables", "-A", "INPUT", "-m", "state", "--state", "ESTABLISHED,RELATED", "-j", "ACCEPT"], check=False)

            # Allow only HTTP traffic on port 8080
            subprocess.run(["sudo", "iptables", "-A", "INPUT", "-p", "tcp", "--dport", "8080", "-j", "ACCEPT"], check=False)
            print("✓ Allowing HTTP traffic on port 8080")

            # Block specific IP range (example: .100-.115)
            network_base = ".".join(self.current_ip.split('.')[:-1])
            blocked_range = f"{network_base}.100/28"  # Blocks .100-.115
            subprocess.run(["sudo", "iptables", "-A", "INPUT", "-s", blocked_range, "-j", "DROP"], check=False)
            print(f"✓ Blocked IP range: {blocked_range}")

            # Allow outbound traffic to backend server
            subprocess.run(["sudo", "iptables", "-A", "OUTPUT", "-p", "tcp", "-d", self.target_host, "--dport", str(self.target_port), "-j", "ACCEPT"], check=False)
            print(f"✓ Allowing outbound traffic to backend {self.target_host}:{self.target_port}")

            # Allow SSH (port 22) to maintain connection
            subprocess.run(["sudo", "iptables", "-A", "INPUT", "-p", "tcp", "--dport", "22", "-j", "ACCEPT"], check=False)

            print("✅ Firewall rules applied successfully!")

        except Exception as e:
            print(f"⚠ Firewall setup failed: {e}")
            print("Continuing without firewall rules...")

    def handle_client(self, client_socket, addr):
        """Handle individual client connections and forward to target"""
        target_socket = None
        try:
            print(f"📥 New connection from {addr}")

            # Set socket timeout to prevent hanging
            client_socket.settimeout(30)

            # Receive request
            request_data = b""
            while True:
                try:
                    chunk = client_socket.recv(1024)
                    if not chunk:
                        break
                    request_data += chunk
                    # Check if we have complete HTTP headers
                    if b'\r\n\r\n' in request_data:
                        break
                except socket.timeout:
                    print(f"⚠ Timeout receiving request from {addr}")
                    return

            if not request_data:
                print(f"⚠ No data received from {addr}")
                return

            # Parse HTTP request
            request_str = request_data.decode('utf-8', errors='ignore')
            lines = request_str.split('\n')
            if lines:
                first_line = lines[0].strip()
                print(f"📋 Request: {first_line}")

                # Extract method and path
                try:
                    parts = first_line.split()
                    if len(parts) >= 2:
                        method, path = parts[0], parts[1]
                        print(f"🔄 Forwarding {method} {path} to backend")
                    else:
                        print(f"⚠ Invalid HTTP request format: {first_line}")
                except Exception as e:
                    print(f"⚠ Error parsing request: {e}")

            # Connect to backend server
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_socket.settimeout(10)

            try:
                target_socket.connect((self.target_host, self.target_port))
                print(f"🔗 Connected to backend {self.target_host}:{self.target_port}")
            except Exception as e:
                print(f"❌ Failed to connect to backend: {e}")
                # Send 502 Bad Gateway response
                error_response = (
                    "HTTP/1.1 502 Bad Gateway\r\n"
                    "Content-Type: text/html\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                    "<html><body><h1>502 Bad Gateway</h1>"
                    "<p>The reverse proxy cannot connect to the backend server.</p>"
                    f"<p>Backend: {self.target_host}:{self.target_port}</p>"
                    "</body></html>\r\n"
                )
                client_socket.sendall(error_response.encode('utf-8'))
                return

            # Forward request to backend
            target_socket.sendall(request_data)
            print(f"📤 Forwarded {len(request_data)} bytes to backend")

            # Receive response from backend
            response_data = b""
            target_socket.settimeout(10)

            while True:
                try:
                    chunk = target_socket.recv(4096)
                    if not chunk:
                        break
                    response_data += chunk
                except socket.timeout:
                    print("⚠ Timeout receiving response from backend")
                    break
                except Exception as e:
                    print(f"⚠ Error receiving from backend: {e}")
                    break

            if response_data:
                # Forward response to client
                client_socket.sendall(response_data)
                print(f"📤 Forwarded {len(response_data)} bytes to client")

                # Log response status
                response_str = response_data.decode('utf-8', errors='ignore')
                if response_str:
                    first_line = response_str.split('\n')[0].strip()
                    print(f"📋 Response: {first_line}")
            else:
                print("⚠ No response received from backend")
                # Send 504 Gateway Timeout
                error_response = (
                    "HTTP/1.1 504 Gateway Timeout\r\n"
                    "Content-Type: text/html\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                    "<html><body><h1>504 Gateway Timeout</h1>"
                    "<p>The backend server did not respond in time.</p>"
                    "</body></html>\r\n"
                )
                client_socket.sendall(error_response.encode('utf-8'))

            print(f"✅ Request from {addr} completed successfully")

        except Exception as e:
            print(f"❌ Error handling client {addr}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Clean up connections
            try:
                if target_socket:
                    target_socket.close()
                client_socket.close()
            except:
                pass

    def start(self):
        """Start the reverse proxy server"""
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.proxy_host, self.proxy_port))
            server_socket.listen(10)

            print(f"🚀 Reverse proxy listening on {self.current_ip}:{self.proxy_port}")
            print(f"🎯 Forwarding requests to {self.target_host}:{self.target_port}")
            print("📡 Waiting for connections...")
            print("-" * 60)

            while True:
                try:
                    client_socket, addr = server_socket.accept()

                    # Handle each client in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, addr),
                        daemon=True
                    )
                    client_thread.start()

                except KeyboardInterrupt:
                    print("\n🛑 Reverse proxy shutting down...")
                    break
                except Exception as e:
                    print(f"❌ Error accepting connection: {e}")

        except Exception as e:
            print(f"❌ Failed to start reverse proxy: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                server_socket.close()
            except:
                pass

if __name__ == "__main__":
    print("🔄 Starting Reverse Proxy Server...")
    print("=" * 60)
    proxy = ReverseProxy()