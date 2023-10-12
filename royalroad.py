#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import base64
import time
import os
import errno
import argparse
from urllib.parse import urljoin
import concurrent.futures
from PIL import Image
import io
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from ebooklib import epub
import tempfile

logging.basicConfig()
logger = logging.getLogger(__name__)

import argparse

p = argparse.ArgumentParser()
p.add_argument('url', type=str)
p.add_argument('--pagenum', type=int, default=1)
p.add_argument('--verbose', '-v', action='count', default=0)
args = p.parse_args()
logger.setLevel(max(logging.WARN - args.verbose * 10, 1))

pd = requests.get(args.url, headers={'User-Agent': 'Mozilla/5.0'})
parse = BeautifulSoup(pd.text, 'html.parser')
title = parse.find('title').string.replace('| Royal Road', '')

book = epub.EpubBook()
book.spine.append('nav')
try:
    book.add_author(parse.find('span', {'property': 'name'}).text.strip())
except:
    pass
toc = []

# define CSS style
style = 'img {width: 70rem; display: block; max-width: 100%; margin: auto;}'
nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)

# add CSS file
book.add_item(nav_css)

nextUrl = urljoin(args.url, parse.find('span', string='Start Reading').find_parent('a').get('href'))

def fetchImage(url: str):
    for i in range(5):
        try:
            with requests.get(url, headers={'User-Agent': 'Mozilla/5.0', 'referer': 'https://readmanganato.com/'}) as response:
                response.raise_for_status()
                with io.BytesIO(response.content) as image_bytes, io.BytesIO() as img_dst:
                    with Image.open(image_bytes) as img:
                        img.save(img_dst, format=img.format, quality=50, optimize=True)
                        return f'<img src=\"data:image/{img.format};base64, {base64.b64encode(img_dst.getvalue()).decode()}\">\n'
        except Exception as err:
            logger.error(err)

while nextUrl is not None:
    errCnt = 0
    try:
        with requests.get(nextUrl, headers={'User-Agent': 'Mozilla/5.0'}) as pageDump:
            parse = BeautifulSoup(pageDump.text, 'html.parser')
            chTitle = parse.find('div', {'class': 'fic-header'}).find('h1').text
            c = epub.EpubHtml(title=chTitle, file_name=f'page{args.pagenum:03d}.html')
            toc.append(c)
            c.write(f'<h1>{chTitle}</h1>')
            for chDiv in parse.find_all('div', {'class': 'chapter-content'}):
                c.write(str(chDiv))
            book.add_item(c)
            book.spine.append(c)
        
            nextLinks = [x for x in parse.find_all(name='a') if 'Next' in x.text]
            if nextLinks:
                next=nextLinks[0]
            args.pagenum += 1
            if next:
                try:
                    nextUrl = urljoin(nextUrl, next.get('href'))
                except:
                    pass
            else:
                next = None
            logger.info(f'New Page {args.pagenum}, next {nextUrl}')
            time.sleep(2)
    except Exception as err:
        errCnt += 1
        logger.error(err)
        if errCnt > 5:
            exit(1)
        else:
            logger.error('Retrying')
    else:
        errCnt = 0

# add navigation files
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())
book.toc = toc
    
# write to the file
epub.write_epub(f"{title}.epub", book, {})