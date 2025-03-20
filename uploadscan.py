import requests
import concurrent.futures
import sys
import time
import argparse
import csv
import os
from urllib.parse import urlparse
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import mimetypes

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def normalize_url(url):
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
    return url.rstrip('/')

def check_upload_form(url, timeout=10, verify_ssl=False, user_agent=None):
    """Check for common upload form paths."""
    upload_paths = [
        '/upload.php', '/uploader.php', '/file-upload.php', '/admin/upload.php', '/uploads/', '/upload/'
    ]
    
    headers = {
        'User-Agent': user_agent or 'UploadScanner/1.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml',
        'Connection': 'close'
    }
    
    results = []
    
    for path in upload_paths:
        target_url = normalize_url(url) + path
        start_time = time.time()
        
        try:
            response = requests.get(target_url, timeout=timeout, verify=verify_ssl, headers=headers, allow_redirects=True)
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                results.append({
                    'url': url,
                    'path': path,
                    'status': 'FOUND',
                    'code': response.status_code,
                    'time': f"{elapsed_time:.2f}s",
                    'message': f"✅ Upload form found at: {target_url}"
                })
            else:
                results.append({
                    'url': url,
                    'path': path,
                    'status': 'NOT_FOUND',
                    'code': response.status_code,
                    'time': f"{elapsed_time:.2f}s",
                    'message': f"❌ Upload form not found (Status: {response.status_code}): {target_url}"
                })
        except requests.exceptions.RequestException as e:
            results.append({
                'url': url,
                'path': path,
                'status': 'ERROR',
                'code': None,
                'time': f"{time.time() - start_time:.2f}s",
                'message': f"❗ Error checking {target_url}: {e}"
            })
    
    return results

def attempt_upload(url, file_path, timeout=10, verify_ssl=False, user_agent=None):
    """Attempt to upload a file to the specified URL."""
    start_time = time.time()
    
    try:
        filename = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(filename)
        
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        files = {'file': (filename, open(file_path, 'rb'), mime_type)}
        
        headers = {
            'User-Agent': user_agent or 'UploadScanner/1.0',
            'Connection': 'close'
        }
        
        response = requests.post(url, files=files, timeout=timeout, verify=verify_ssl, headers=headers, allow_redirects=True)
        elapsed_time = time.time() - start_time
        
        if response.status_code == 200:
            return {
                'url': url,
                'status': 'UPLOAD_SUCCESS',
                'code': response.status_code,
                'time': f"{elapsed_time:.2f}s",
                'message': f"🚀 File uploaded successfully to: {url}"
            }
        else:
            return {
                'url': url,
                'status': 'UPLOAD_FAILED',
                'code': response.status_code,
                'time': f"{elapsed_time:.2f}s",
                'message': f"❌ File upload failed (Status: {response.status_code}): {url}"
            }
    except requests.exceptions.RequestException as e:
        return {
            'url': url,
            'status': 'UPLOAD_ERROR',
            'code': None,
            'time': f"{time.time() - start_time:.2f}s",
            'message': f"❗ Error uploading to {url}: {e}"
        }

def scan_websites_for_uploads(websites, workers=10, timeout=10, verify_ssl=False, user_agent=None, upload_file=None):
    """Scan websites for upload forms and attempt uploads."""
    results = []
    total = len(websites)
    completed = 0
    
    print(f"Starting scan of {total} websites with {workers} concurrent connections...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_url = {executor.submit(check_upload_form, url, timeout, verify_ssl, user_agent): url for url in websites}
        
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                upload_form_results = future.result()
                results.extend(upload_form_results)
                
                for form_result in upload_form_results:
                    if form_result['status'] == 'FOUND' and upload_file:
                        upload_result = attempt_upload(
                            normalize_url(url) + form_result['path'], upload_file, timeout, verify_ssl, user_agent
                        )
                        results.append(upload_result)
                
                completed += 1
                progress = (completed / total) * 100
                sys.stdout.write(f"\rProgress: [{completed}/{total}] {progress:.1f}% - Checking: {url}")
                sys.stdout.flush()
                
            except Exception as e:
                results.append({
                    'url': url,
                    'status': 'EXCEPTION',
                    'code': None,
                    'time': 'N/A',
                    'message': f"❗ Exception processing {url}: {e}"
                })
                
    print("\nScan completed!")
    return results

# Fungsi load_urls_from_file dan export_results tetap sama seperti sebelumnya.
def load_urls_from_file(filename):
    urls = []
    try:
        file_extension = filename.split('.')[-1].lower()
        if file_extension == 'csv':
            with open(filename, 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row and len(row) > 0 and row[0].strip():
                        urls.append(row[0].strip())
        else:
            with open(filename, 'r') as f:
                for line in f:
                    url = line.strip()
                    if url and not url.startswith('#'):
                        urls.append(url)
        return urls
    except Exception as e:
        print(f"Error loading URLs from file {filename}: {e}")
        return []

def export_results(results, output_format, filename=None):
    if output_format == 'csv' and filename:
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['URL', 'Status', 'Status Code', 'Response Time', 'Message'])
                for result in results:
                    writer.writerow([
                        result['url'],
                        result['status'],
                        result['code'],
                        result['time'],
                        result['message']
                    ])
            print(f"Results exported to {filename}")
        except Exception as e:
            print(f"Error exporting results to CSV: {e}")
    else:
        total = len(results)
        found = sum(1 for r in results if r['status'] == 'FOUND' or r['status'] == 'UPLOAD_SUCCESS')
        errors = sum(1 for r in results if r['status'] not in ['FOUND', 'NOT
