import os
import requests
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from colorama import Fore, Style, init
from tqdm import tqdm

init(autoreset=True)

page_url = input(Fore.CYAN + "Enter the URL of the page to clone: " + Style.RESET_ALL).strip()
site_name = input(Fore.CYAN + "Enter the name for the cloned site folder: " + Style.RESET_ALL).strip()

chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=chrome_options)

output_dir = site_name
folders = {
    "html": "",
    "css": "css",
    "js": "js",
    "images": "images",
    "fonts": "fonts",
    "other": "assets"
}

for folder in folders.values():
    os.makedirs(os.path.join(output_dir, folder), exist_ok=True)

def download_file(url, folder_name):
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            filename = os.path.join(output_dir, folder_name, os.path.basename(urlparse(url).path))
            with open(filename, 'wb') as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            print(Fore.GREEN + f"[SUCCESS] Downloaded: {url}")
            return filename
    except requests.exceptions.RequestException as e:
        print(Fore.RED + f"[ERROR] Failed to download {url}: {e}")
    return None

def download_and_update_fonts(css_content, base_url):
    font_extensions = (".woff", ".woff2", ".ttf", ".otf", ".eot", ".svg")
    font_urls = set()
    updated_css_content = css_content
    for line in css_content.splitlines():
        if "url(" in line:
            start = line.find("url(") + 4
            end = line.find(")", start)
            font_url = line[start:end].strip('"').strip("'")
            full_url = urljoin(base_url, font_url)
            if full_url.endswith(font_extensions):
                font_urls.add(full_url)
                local_font_path = download_file(full_url, folders["fonts"])
                if local_font_path:
                    updated_css_content = updated_css_content.replace(font_url, os.path.relpath(local_font_path, os.path.join(output_dir, folders["css"])))
    return updated_css_content

def adjust_html_paths(soup, page_url):
    asset_count = len(soup.find_all("link", {"rel": "stylesheet"})) + \
                  len(soup.find_all("script", {"src": True})) + \
                  len(soup.find_all("img")) + \
                  len(soup.find_all(["audio", "video", "source"]))

    with tqdm(total=asset_count, desc="Cloning Progress", bar_format="{l_bar}{bar} {n_fmt}/{total_fmt}", colour="green") as progress_bar:
        for css in soup.find_all("link", {"rel": "stylesheet"}):
            css_url = css.get("href")
            if css_url:
                full_css_url = urljoin(page_url, css_url)
                css_response = requests.get(full_css_url)
                if css_response.status_code == 200:
                    updated_css_content = download_and_update_fonts(css_response.text, full_css_url)
                    local_css_path = os.path.join(output_dir, folders["css"], os.path.basename(urlparse(css_url).path))
                    with open(local_css_path, "w", encoding="utf-8") as css_file:
                        css_file.write(updated_css_content)
                    css['href'] = os.path.relpath(local_css_path, output_dir)
            progress_bar.update(1)

        for script in soup.find_all("script", {"src": True}):
            js_url = script.get("src")
            if js_url:
                local_js_path = download_file(urljoin(page_url, js_url), folders["js"])
                if local_js_path:
                    script['src'] = os.path.relpath(local_js_path, output_dir)
            progress_bar.update(1)

        for img in soup.find_all("img"):
            img_url = img.get("src")
            if img_url:
                local_img_path = download_file(urljoin(page_url, img_url), folders["images"])
                if local_img_path:
                    img['src'] = os.path.relpath(local_img_path, output_dir)
            progress_bar.update(1)

        for tag in soup.find_all(["audio", "video", "source"]):
            asset_url = tag.get("src")
            if asset_url:
                local_asset_path = download_file(urljoin(page_url, asset_url), folders["other"])
                if local_asset_path:
                    tag['src'] = os.path.relpath(local_asset_path, output_dir)
            progress_bar.update(1)

def clone_page(page_url):
    try:
        print(Fore.BLUE + "[INFO] Loading page in browser...")
        driver.get(page_url)
        time.sleep(10)

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")

        print(Fore.YELLOW + "[INFO] Adjusting paths and downloading assets...")
        adjust_html_paths(soup, page_url)

        for style_tag in soup.find_all("style"):
            updated_style_content = download_and_update_fonts(style_tag.text, page_url)
            style_tag.string = updated_style_content

        html_file = os.path.join(output_dir, "index.html")
        with open(html_file, "w", encoding="utf-8") as file:
            file.write(soup.prettify())
        print(Fore.GREEN + "[SUCCESS] Saved modified HTML as index.html")

    except Exception as e:
        print(Fore.RED + f"[ERROR] An error occurred: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    print(Fore.CYAN + "[INFO] Starting the cloning process...\n")
    clone_page(page_url)
    print(Fore.CYAN + "\n[INFO] Cloning process completed!")
