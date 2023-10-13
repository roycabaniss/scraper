#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import argparse
import os
import errno
import logging
import queue
import zipfile
import threading
import concurrent.futures
import io
import time
from PIL import Image

p = argparse.ArgumentParser()
p.add_argument('url', type=str)
p.add_argument('--pagenum', type=int, default=1)
p.add_argument('--start', type=int, default=0)
p.add_argument('--end', type=int, default=-1)
p.add_argument('--verbose', '-v', action='count', default=0)
args = p.parse_args()

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(max(logging.WARN - args.verbose * 10, 1))


pd = requests.get(args.url, headers={'User-Agent': 'Mozilla/5.0'})
parse = BeautifulSoup(pd.text, 'html.parser')
title = parse.find('title').string.replace(' - MANHUAUS.COM', '')
try:
    os.makedirs(title)
except OSError as e:
    if e.errno != errno.EEXIST:
        raise
Finished = "This task is finished. No, really."

def fetchImage(imgUrl):
    logger.debug(f'fetchImage {imgUrl}')
    response = requests.get(imgUrl)
    response.raise_for_status()
    for _ in range(5):
        try:
            with io.BytesIO(response.content) as image_bytes, io.BytesIO() as img_dst:
                with Image.open(image_bytes) as img:
                    format = {'jpg': 'JPEG', 'webp': 'JPEG'}.get(img.format.lower(), img.format)
                    logger.debug(f'format {format}')
                    img.save(img_dst, format=format, quality=20, optimize=True)
                    return (format, img_dst.getvalue())
        except Exception as err:
            logger.error(f'fetchImage({imgUrl} failed)')
            logger.error(err)
            time.sleep(2)
        

def writeToCbr(writeQueue, path):
    logger.debug(f'writeToCbr(queue, {path})')
    with open(path, 'wb') as zipdst:
        with zipfile.ZipFile(zipdst, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as dstFile:
            imgNum = 1
            while True:
                task = writeQueue.get()
                if task == Finished:
                    writeQueue.task_done()
                    return
                format, content = task.result()
                logger.info(f"writing {imgNum}")
                dstFile.writestr(f'{imgNum:03d}.{format}', content)
                imgNum += 1
                writeQueue.task_done()

def downloadChapter(url, num):
    logger.debug(f'downloadChapter({url}, {num})')
    writeQueue = queue.Queue(maxsize=8)
    threading.Thread(target=writeToCbr, args=(writeQueue, os.path.join(title, f'chapter_{num:03d}.cbr'),)).start()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        with requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as pageDump:
            parse = BeautifulSoup(pageDump.text, 'html.parser')
            siw = parse.find('div', {'class':'reading-content'})
            for img in siw.find_all('img'):
                writeQueue.put(executor.submit(fetchImage, (img.get('data-src') or img.get('src')).strip()))
            writeQueue.put(Finished)

with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
    for num, chapterUrl in enumerate([li.a.get('href') for li in parse.find('ul', {'class': 'version-chap'}).find_all('li')[::-1]], start=args.pagenum):
        executor.submit(downloadChapter, chapterUrl, num)