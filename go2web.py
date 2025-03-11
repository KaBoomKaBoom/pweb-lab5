#!/usr/bin/env python3
import sys
import socket
import argparse
import re
import os
import json
import datetime
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlencode, quote_plus

# Cache management
class Cache:
    def __init__(self, cache_dir=".go2web_cache"):
        self.cache_dir = cache_dir
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            
    def get_cache_path(self, url, content_type=None):
        # Create a filename based on the URL
        filename = url.replace("://", "_").replace("/", "_").replace("?", "_").replace("&", "_")
        if content_type:
            filename += f"_{content_type}"
        return os.path.join(self.cache_dir, filename)
    
    def get(self, url, content_type=None, max_age=3600):  # Default cache age: 1 hour
        cache_path = self.get_cache_path(url, content_type)
        
        if os.path.exists(cache_path):
            # Check if cache is still valid
            modified_time = os.path.getmtime(cache_path)
            if (datetime.datetime.now().timestamp() - modified_time) < max_age:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                return cache_data.get('response'), cache_data.get('headers')
        return None, None
    
    def set(self, url, response, headers, content_type=None):
        cache_path = self.get_cache_path(url, content_type)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump({
                'response': response,
                'headers': headers
            }, f)

# HTTP client implementation
def make_http_request(url, method="GET", headers=None, data=None, follow_redirects=True, accept=None, max_redirects=5):
    cache = Cache()
    
    # Parse URL
    parsed_url = urlparse(url)
    hostname = parsed_url.netloc
    path = parsed_url.path if parsed_url.path else "/"
    if parsed_url.query:
        path += "?" + parsed_url.query
    port = parsed_url.port if parsed_url.port else 80 if parsed_url.scheme == "http" else 443
    
    # Setup default headers
    if headers is None:
        headers = {}
    headers["Host"] = hostname.split(":")[0]
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    headers["Connection"] = "close"
    
    if accept:
        headers["Accept"] = accept
    
    # Check cache before making request
    if method == "GET" and accept:
        cached_response, cached_headers = cache.get(url, accept)
        if cached_response:
            print("Using cached response")
            return cached_response, cached_headers
    elif method == "GET":
        cached_response, cached_headers = cache.get(url)
        if cached_response:
            print("Using cached response")
            return cached_response, cached_headers
    
    # Prepare request
    request = f"{method} {path} HTTP/1.1\r\n"
    for key, value in headers.items():
        request += f"{key}: {value}\r\n"
    
    if data:
        request += f"Content-Length: {len(data)}\r\n"
    
    request += "\r\n"
    if data:
        request += data
    
    try:
        # Create socket connection
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Handle HTTPS
        if parsed_url.scheme == "https":
            import ssl
            context = ssl.create_default_context()
            s = context.wrap_socket(s, server_hostname=hostname.split(":")[0])
        
        s.connect((hostname.split(":")[0], port))
        s.sendall(request.encode())
        
        # Receive response
        response = b""
        while True:
            data = s.recv(4096)
            if not data:
                break
            response += data
        
        s.close()
        
        # Parse response
        try:
            header_end = response.find(b"\r\n\r\n")
            headers_raw = response[:header_end].decode("utf-8", errors="ignore")
            body = response[header_end + 4:]
            
            # Extract status code and headers
            status_line = headers_raw.split("\r\n")[0]
            status_code = int(status_line.split(" ")[1])
            response_headers = {}
            
            for header_line in headers_raw.split("\r\n")[1:]:
                if ":" in header_line:
                    key, value = header_line.split(":", 1)
                    response_headers[key.strip()] = value.strip()
            
            # Handle redirects
            if follow_redirects and status_code in (301, 302, 303, 307, 308) and "Location" in response_headers and max_redirects > 0:
                redirect_url = response_headers["Location"]
                
                # Handle relative URLs
                if not redirect_url.startswith(("http://", "https://")):
                    if redirect_url.startswith("/"):
                        redirect_url = f"{parsed_url.scheme}://{hostname}{redirect_url}"
                    else:
                        redirect_url = f"{parsed_url.scheme}://{hostname}/{redirect_url}"
                
                print(f"Redirecting to: {redirect_url}")
                return make_http_request(redirect_url, method, headers, data, follow_redirects, accept, max_redirects - 1)
                
            # Decode body based on Content-Type
            content_type = response_headers.get("Content-Type", "")
            charset = "utf-8"  # default charset
            
            if "charset=" in content_type:
                charset = content_type.split("charset=")[1].split(";")[0].strip()
            
            # Handle Content-Encoding if present
            if "Content-Encoding" in response_headers:
                encoding = response_headers["Content-Encoding"].lower()
                if encoding == "gzip":
                    import gzip
                    try:
                        body = gzip.decompress(body)
                    except OSError:
                        print("Error: Not a gzipped file")
                        return body.decode(charset, errors="replace"), response_headers
                elif encoding == "deflate":
                    import zlib
                    try:
                        body = zlib.decompress(body)
                    except zlib.error:
                        print("Error: Not a deflated file")
                        return body.decode(charset, errors="replace"), response_headers
            
            try:
                decoded_body = body.decode(charset, errors="replace")
            except (UnicodeDecodeError, LookupError):
                decoded_body = body.decode("utf-8", errors="replace")
            try:
                decoded_body = body.decode(charset, errors="replace")
            except (UnicodeDecodeError, LookupError):
                decoded_body = body.decode("utf-8", errors="replace")
                        # Cache the response
            if method == "GET" and status_code == 200:
                if accept:
                    cache.set(url, decoded_body, response_headers, accept)
                else:
                    cache.set(url, decoded_body, response_headers)
            
            return decoded_body, response_headers
            
        except Exception as e:
            return f"Error parsing response: {str(e)}", {}
            
    except Exception as e:
        return f"Error making HTTP request: {str(e)}", {}
    
def search(term, search_engine="duckduckgo"):
    if search_engine == "duckduckgo":
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(term)}"
        print(f"Searching for: {search_url}")
        response, headers = make_http_request(search_url)
        
        soup = BeautifulSoup(response, 'html.parser')
        links = []
        for result in soup.find_all('div', class_='result__body'):
            a_tag = result.find('a', class_='result__a')
            if a_tag and 'href' in a_tag.attrs:
                link = a_tag['href']
                if link.startswith("//duckduckgo.com/l/?uddg="):
                    actual_url = link.split("uddg=")[1].split("&")[0]
                    actual_url = actual_url.replace("%3A", ":").replace("%2F", "/")
                    links.append((a_tag.get_text(), actual_url))
                    if len(links) >= 10:
                        break
        
        return links
    else:
        return []