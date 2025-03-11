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