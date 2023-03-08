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
p.add_argument('--verbose', '-v', action='count', default=0)
args = p.parse_args()

logger.setLevel(max(logging.WARN - args.verbose * 10, 1))
pd = requests.get(args.url, headers={'User-Agent': 'Mozilla/5.0'})
parse = BeautifulSoup(pd.text, 'html.parser')
title = parse.find('title').string.replace(' - Asura Scans', '')

nextUrl = parse.find('ul', {'class': 'clstyle'}).find_all('li')[-1].a.get('href')

def fetchImage(url: str, referer: str):
    for i in range(5):
        try:
            with requests.get(url, headers={'User-Agent': 'Mozilla/5.0', 'referer': referer}) as response:
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

def downloadChapter(nextUrl: str, pagenum: int):
    errCnt = 0
    
    for _ in range(5):
        try:
            with open(os.path.join(title, f'chapter{pagenum:03d}.cbr'), 'wb') as zipdst:
                with zipfile.ZipFile(zipdst, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as dstFile:
                    logger.info(nextUrl)
                    with requests.get(nextUrl, headers={'User-Agent': 'Mozilla/5.0'}) as pageDump:
                        parse = BeautifulSoup(pageDump.text, 'html.parser')
                        siw = parse.find('div', {'id':'readerarea'})
                        # We can use a with statement to ensure threads are cleaned up promptly
                        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                            imgTasks = [executor.submit(fetchImage, urljoin(nextUrl, img.get('src')), nextUrl) for img in siw.find_all('img')]
                            for idx, task in enumerate(imgTasks):
                                format, content = task.result()
                                dstFile.writestr(f'{idx:03d}.{format}', content)
        except Exception as err:
            errCnt += 1
            logger.error(err)
            if errCnt > 5:
                exit(1)
            else:
                logger.error('Retrying')
        else:
            return

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    for idx, url in enumerate([x.a.get('href') for x in parse.find('ul', {'class': 'clstyle'}).find_all('li')[::-1]]):
        executor.submit(downloadChapter, url, idx)

