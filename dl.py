# coding=utf-8
import sys, os, glob
import re
import requests
import json
import wget
from bs4 import BeautifulSoup
from yt_dlp import YoutubeDL
import base64
import concurrent.futures
import random
import time
from urllib.parse import urlparse

# List of common user agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Create a session that persists across requests
session = requests.Session()


def get_browser_headers(url=None):
    """Generate realistic browser headers with optional referer based on URL"""
    parsed_url = urlparse(url) if url else None
    referer = f"{parsed_url.scheme}://{parsed_url.netloc}/" if parsed_url else ""

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none" if not referer else "same-origin",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "DNT": "1",
        "Priority": "u=1"
    }

    if referer:
        headers["Referer"] = referer

    return headers


def main():
    args = sys.argv  # saving the cli arguments into args

    try:
        args[1]     #try if args has a value at index 1
    except IndexError:
        print("Please use a parameter. Use -h for Help") #if not, tells the user to specify an argument
        quit()

    if args[1] == "-h":     #if the first user argument is "-h" call the help function
        help()
    elif args[1] == "-u":   #if the first user argument is "-u" call the download function
        URL = args[2]
        download(URL)
    elif args[1] == "-l":   #if the first user argument is "-l" call the list_dl (list download) function
        doc = args[2]
        list_dl(doc)
    else:
        URL = args[1]       #if the first user argument is the <URL> call the download function
        download(URL)

def help():
    print("Version v1.3.1 (Forked by HerobrineTVv)")
    print("Fixxed issues with finding the Download Links")
    print("")
    print("______________")
    print("Arguments:")
    print("-h shows this help")
    print("-u <URL> downloads the <URL> you specify")
    print("-l <doc> opens the <doc> you specify and downloads every URL line after line")
    print("<URL> just the URL as Argument works the same as with -u Argument")
    print("______________")
    print("")
    print("Credits to @NikOverflow, @cuitrlal and @cybersnash on GitHub for contributing")

def list_dl(doc):
    """
    Reads lines from the specified doc file and downloads them in parallel.
    Lines starting with '#' and empty lines are ignored.
    """
    tmp_list = open(doc).readlines()
    fixed_list = [el for el in tmp_list if not el.startswith('#')]
    lines = [link.strip() for link in fixed_list if link.strip()]

    # Execute parallel downloads with up to 4 threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_link = {executor.submit(download, link): link for link in lines}

        for i, future in enumerate(concurrent.futures.as_completed(future_to_link), start=1):
            link = future_to_link[future]
            print(f"Download {i} / {len(lines)}")
            print(f"echo Link: {link}")
            try:
                future.result()
            except Exception as e:
                print(f"[!] Error downloading {link}: {e}")

    # Remove .part files after all downloads are complete
    delpartfiles()


def download(URL):
    URL = str(URL)

    # Add a small random delay to mimic human behavior
    time.sleep(random.uniform(1, 3))

    # Get browser-like headers
    headers = get_browser_headers(URL)

    try:
        # Use the session for persistent cookies
        html_page = session.get(URL, headers=headers, timeout=30)
        html_page.raise_for_status()  # Raise exception for 4XX/5XX responses

        # Handle cloudflare or other protection
        if html_page.status_code == 403 or "captcha" in html_page.text.lower():
            print(f"[!] Access denied or captcha detected for {URL}. Trying with different headers...")
            # Try again with different headers after a delay
            time.sleep(random.uniform(3, 5))
            headers = get_browser_headers(URL)
            headers["User-Agent"] = random.choice(USER_AGENTS)  # Force different UA
            html_page = session.get(URL, headers=headers, timeout=30)
            html_page.raise_for_status()

        soup = BeautifulSoup(html_page.content, 'html.parser')

        #print(html_page.text)

        redirect_patterns = [
            "window.location.href = '",
            "window.location = '",
            "location.href = '",
            "window.location.replace('",
            "window.location.assign('",
            "window.location=\"",
            "window.location.href=\""
        ]

        # Check for redirects in any script tag
        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string:
                for pattern in redirect_patterns:
                    if pattern in script.string:
                        L = len(pattern)
                        i0 = script.string.find(pattern)
                        closing_quote = "'" if pattern.endswith("'") else "\""
                        i1 = script.string.find(closing_quote, i0 + L)
                        if i1 > i0:
                            url = script.string[i0 + L:i1]
                            print(f"[*] Detected redirect to: {url}")
                            return download(url)

        # Try multiple methods to find the title
        name = None
        for meta_tag in ['og:title', 'twitter:title', 'title']:
            name_find = soup.find('meta', attrs={"property": meta_tag}) or soup.find('meta', attrs={"name": meta_tag})
            if name_find and name_find.get("content"):
                name = name_find["content"]
                break

        # If meta tags fail, try the title tag
        if not name and soup.title and soup.title.string:
            name = soup.title.string

        if name:
            # Clean the filename to avoid issues
            name = re.sub(r'[\\/*?:"<>|]', "_", name)
            name = name.replace(" ", "_")
            print("Name of file: " + name)
        else:
            print("Could not find the name of the file. Using default name.")
            name = URL.split("/")[-1]  # Use the last part of the URL as the default file name
            if not name or name == "":
                name = f"download_{int(time.time())}"
            print("Using default file name: " + name)

        # Enhanced source detection - multiple patterns and approaches
        source_json = None

        # Method 1: Look for "var sources" pattern
        sources_find = soup.find_all(string=re.compile("var sources"))
        if sources_find:
            sources_find = str(sources_find)
            try:
                slice_start = sources_find.index("var sources")
                source = sources_find[slice_start:]
                slice_end = source.index(";")
                source = source[:slice_end]
                source = source.replace("var sources = ", "")
                source = source.replace("\'", "\"")
                source = source.replace("\\n", "")
                source = source.replace("\\", "")

                # Clean up JSON for parsing
                strToReplace = ","
                replacementStr = ""
                source = replacementStr.join(source.rsplit(strToReplace, 1))

                source_json = json.loads(source)
                print("[+] Found sources using var sources pattern")
            except (ValueError, json.JSONDecodeError) as e:
                print(f"[!] Error parsing sources: {e}")
                source_json = None

        # Method 2: Look for script tags with sources
        if not source_json:
            scripts = soup.find_all("script")
            for script in scripts:
                if not script.string:
                    continue

                # Look for different patterns
                patterns = [
                    "var sources",
                    "sources =",
                    "sources:",
                    "\"sources\":",
                    "'sources':"
                ]

                for pattern in patterns:
                    if pattern in script.string:
                        try:
                            # Extract JSON-like structure
                            script_text = script.string

                            # Find the start of the sources object
                            start_idx = script_text.find(pattern)
                            if start_idx == -1:
                                continue

                            # Find the opening brace
                            brace_idx = script_text.find("{", start_idx)
                            if brace_idx == -1:
                                continue

                            # Count braces to find the matching closing brace
                            brace_count = 1
                            end_idx = brace_idx + 1

                            while brace_count > 0 and end_idx < len(script_text):
                                if script_text[end_idx] == "{":
                                    brace_count += 1
                                elif script_text[end_idx] == "}":
                                    brace_count -= 1
                                end_idx += 1

                            if brace_count == 0:
                                json_str = script_text[brace_idx:end_idx]
                                # Clean up the JSON string
                                json_str = json_str.replace("'", "\"")

                                # Try to parse the JSON
                                try:
                                    source_json = json.loads(json_str)
                                    print(f"[+] Found sources using pattern: {pattern}")
                                    break
                                except json.JSONDecodeError:
                                    pass
                        except Exception as e:
                            print(f"[!] Error extracting sources from script: {e}")

                if source_json:
                    break

        # Method 3: Look for data attributes in video tags
        if not source_json:
            video_tags = soup.find_all("video")
            for video in video_tags:
                src = video.get("src")
                if src:
                    print(f"[+] Found direct video source: {src}")
                    source_json = {"mp4": src}
                    break

                # Check for source tags inside video
                source_tags = video.find_all("source")
                if source_tags:
                    for source_tag in source_tags:
                        src = source_tag.get("src")
                        if src:
                            type_attr = source_tag.get("type", "")
                            if "mp4" in type_attr:
                                source_json = {"mp4": src}
                            elif "m3u8" in type_attr or "hls" in type_attr:
                                source_json = {"hls": src}
                            else:
                                source_json = {"mp4": src}  # Default to mp4
                            print(f"[+] Found video source from source tag: {src}")
                            break

                if source_json:
                    break

        # Method 4: Look for m3u8 or mp4 URLs in the page
        if not source_json:
            print("[*] Searching for direct media URLs in page...")
            # Look for m3u8 URLs
            m3u8_pattern = r'(https?://[^"\']+\.m3u8[^"\'\s]*)'
            m3u8_matches = re.findall(m3u8_pattern, html_page.text)
            if m3u8_matches:
                source_json = {"hls": m3u8_matches[0]}
                print(f"[+] Found HLS URL: {m3u8_matches[0]}")

            # Look for mp4 URLs
            if not source_json:
                mp4_pattern = r'(https?://[^"\']+\.mp4[^"\'\s]*)'
                mp4_matches = re.findall(mp4_pattern, html_page.text)
                if mp4_matches:
                    source_json = {"mp4": mp4_matches[0]}
                    print(f"[+] Found MP4 URL: {mp4_matches[0]}")

        # Method 5: Look for base64 encoded sources
        if not source_json:
            base64_pattern = r'base64[,:]([A-Za-z0-9+/=]+)'
            base64_matches = re.findall(base64_pattern, html_page.text)
            for match in base64_matches:
                try:
                    decoded = base64.b64decode(match).decode('utf-8')
                    if '.mp4' in decoded:
                        source_json = {"mp4": decoded}
                        print(f"[+] Found base64 encoded MP4 URL")
                        break
                    elif '.m3u8' in decoded:
                        source_json = {"hls": decoded}
                        print(f"[+] Found base64 encoded HLS URL")
                        break
                except:
                    continue

        # If we still don't have sources, try to find any iframe that might contain the video
        if not source_json:
            iframes = soup.find_all("iframe")
            if iframes:
                for iframe in iframes:
                    iframe_src = iframe.get("src")
                    if iframe_src:
                        if iframe_src.startswith("//"):
                            iframe_src = "https:" + iframe_src
                        elif not iframe_src.startswith(("http://", "https://")):
                            # Handle relative URLs
                            parsed_url = urlparse(URL)
                            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                            iframe_src = base_url + iframe_src if iframe_src.startswith(
                                "/") else base_url + "/" + iframe_src

                        print(f"[*] Found iframe, following to: {iframe_src}")
                        return download(iframe_src)

        if not source_json:
            print("[!] Could not find sources in the page. The site structure might have changed.")
            print("[*] Dumping page content for debugging...")
            with open(f"debug_page_{int(time.time())}.html", "w", encoding="utf-8") as f:
                f.write(html_page.text)
            print(f"[*] Page content saved for debugging")
            return

        # Process the found sources
        try:
            if "mp4" in source_json:
                link = source_json["mp4"]
                # Check if the link is base64 encoded
                if isinstance(link, str) and (link.startswith("eyJ") or re.match(r'^[A-Za-z0-9+/=]+$', link)):
                    try:
                        link = base64.b64decode(link).decode("utf-8")
                        print("[+] Successfully decoded base64 MP4 URL")
                    except Exception as e:
                        print(f"[!] Failed to decode base64: {e}")

                # Ensure the link is a complete URL
                if link.startswith("//"):
                    link = "https:" + link

                basename, ext = os.path.splitext(name)
                if not ext:
                    ext = ".mp4"
                name = f"{basename}_SS{ext}"

                print(f"[*] Downloading MP4 stream: {link}")
                ydl_opts = {
                    'outtmpl': name,
                    'quiet': False,
                    'no_warnings': False,
                    'http_headers': headers
                }
                with YoutubeDL(ydl_opts) as ydl:
                    try:
                        ydl.download([link])
                    except Exception as e:
                        print(f"[!] YoutubeDL error: {e}")
            elif "hls" in source_json:
                link = source_json["hls"]
                # Check if the link is base64 encoded
                if isinstance(link, str) and (link.startswith("eyJ") or re.match(r'^[A-Za-z0-9+/=]+$', link)):
                    try:
                        link = base64.b64decode(link).decode("utf-8")
                        print("[+] Successfully decoded base64 HLS URL")
                    except Exception as e:
                        print(f"[!] Failed to decode base64: {e}")

                # Ensure the link is a complete URL
                if link.startswith("//"):
                    link = "https:" + link

                basename, ext = os.path.splitext(name)
                if not ext:
                    ext = ".mp4"  # HLS streams are typically downloaded as MP4
                name = f"{basename}_SS{ext}"

                print(f"[*] Downloading HLS stream: {link}")
                ydl_opts = {
                    'outtmpl': name,
                    'quiet': False,
                    'no_warnings': False,
                    'http_headers': headers
                }
                with YoutubeDL(ydl_opts) as ydl:
                    try:
                        ydl.download([link])
                    except Exception as e:
                        print(f"[!] YoutubeDL error: {e}")
            else:
                print("[!] Could not find downloadable URL. The site might have changed.")
                print(f"Available keys in source_json: {list(source_json.keys())}")
                for key, value in source_json.items():
                    print(f"{key}: {value}")
        except KeyError as e:
            print(f"[!] KeyError: {e}")
            print("[!] Could not find downloadable URL. The site might have changed.")
            print(f"Available keys in source_json: {list(source_json.keys())}")

    except requests.exceptions.RequestException as e:
        print(f"[!] Request error: {e}")
    except Exception as e:
        print(f"[!] Unexpected error: {e}")

    print("\n")


def download_file(url, filename, referer_url=None):
    """Download file with proper headers and progress tracking"""
    headers = get_browser_headers(referer_url)

    try:
        with session.get(url, headers=headers, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))

            with open(filename, 'wb') as f:
                if total_size == 0:
                    print("[!] Unknown file size. Downloading...")
                    f.write(r.content)
                else:
                    downloaded = 0
                    print(f"[*] File size: {total_size / 1024 / 1024:.2f} MB")
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            done = int(50 * downloaded / total_size)
                            sys.stdout.write(
                                f"\r[{'=' * done}{' ' * (50 - done)}] {downloaded / 1024 / 1024:.2f}/{total_size / 1024 / 1024:.2f} MB")
                            sys.stdout.flush()
            print("\n[+] Download complete!")
    except Exception as e:
        print(f"[!] Error downloading file: {e}")
        # Fall back to wget if our method fails
        print("[*] Falling back to wget...")
        wget.download(url, out=filename)

def delpartfiles():
    path = os.getcwd()
    for file in glob.iglob(os.path.join(path, '*.part')):
        os.remove(file)

if __name__ == "__main__":
    main()