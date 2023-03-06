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
import zipfile

import argparse

logging.basicConfig()
logger = logging.getLogger(__name__)

p = argparse.ArgumentParser()
p.add_argument('url', type=str)
p.add_argument('--pagenum', type=int, default=1)
p.add_argument('--verbose', '-v', action='count', default=0)
args = p.parse_args()

logger.setLevel(max(logging.WARN - args.verbose * 10, 1))
pd = requests.get(args.url, headers={'User-Agent': 'Mozilla/5.0'})
parse = BeautifulSoup(pd.text, 'html.parser')
title = parse.find('title').string.replace(' Manga Online Free - Manganato', '')

nextUrl = parse.find('ul', {'class': 'row-content-chapter'}).find_all('li')[0-args.pagenum].a.get('href')

def fetchImage(url: str):
    for i in range(5):
        try:
            with requests.get(url, headers={'User-Agent': 'Mozilla/5.0', 'referer': 'https://readmanganato.com/'}) as response:
                response.raise_for_status()
                with io.BytesIO(response.content) as image_bytes, io.BytesIO() as img_dst:
                    with Image.open(image_bytes) as img:
                        format = {}.get(img.format.lower(), img.format)
                        img.save(img_dst, format=format, quality=20, optimize=True)
                        return (format, img_dst.getvalue())
        except Exception as err:
            logger.error(err)

try:
    os.makedirs(title)
except OSError as e:
    if e.errno != errno.EEXIST:
        raise
while nextUrl is not None:
    errCnt = 0
    try:
        with open(os.path.join(title, f'page{args.pagenum:03d}.cbr'), 'wb') as zipdst:
            with zipfile.ZipFile(zipdst, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as dstFile:
                logger.info(nextUrl)
                with requests.get(nextUrl, headers={'User-Agent': 'Mozilla/5.0'}) as pageDump:
                    parse = BeautifulSoup(pageDump.text, 'html.parser')
                    siw = parse.find('div', {'class':'container-chapter-reader'})
                    # We can use a with statement to ensure threads are cleaned up promptly
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        imgTasks = [executor.submit(fetchImage, urljoin(nextUrl, img.get('src'))) for img in siw.find_all('img')]
                        for idx, task in enumerate(imgTasks):
                            format, content = task.result()
                            dstFile.writestr(f'{idx:03d}.{format}', content)
                    next = parse.find(name='a', attrs={'class':'navi-change-chapter-btn-next'})
                    if next:
                        nextUrl = urljoin(nextUrl, next.get('href'))
                    else:
                        nextUrl = None
            args.pagenum += 1
            logger.info(f'New Page {args.pagenum}')
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
