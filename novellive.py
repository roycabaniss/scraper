#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import base64
import time
import argparse
from urllib.parse import urljoin
import concurrent.futures
from PIL import Image
import io
import logging
from ebooklib import epub
import threading
import queue
import tempfile
import re

logging.basicConfig()
logger = logging.getLogger(__name__)

import argparse

p = argparse.ArgumentParser()
p.add_argument("url", type=str)
p.add_argument("--pagenum", type=int, default=1)
p.add_argument("--verbose", "-v", action="count", default=0)
p.add_argument("--start", type=int, default=0)
p.add_argument("--end", type=int, default=-1)
args = p.parse_args()
logger.setLevel(max(logging.WARN - args.verbose * 10, 1))

headers= {
    'Host': 'novellive.com',
    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Cookie': '_ga_BS3H552HGD=GS1.1.1702872100.4.1.1702874093.0.0.0; _ga=GA1.1.2057649859.1702785828; __gads=ID=245dfbcec5d91025:T=1702785834:RT=1702874093:S=ALNI_MYzbLyrE_UV-YmDGooO5LNRxYZmsg; __gpi=UID=00000daa5235964d:T=1702785834:RT=1702874093:S=ALNI_MaXA3LRAY0z9G2mGB0soz2ET-cmpg; cf_chl_2=374c8df288e4acd; cf_clearance=OuFP137hpPrE8OKqF_lNU4sPiNobomDyXMlrjVCzIuw-1702874084-0-1-f456854e.dd47656a.a357daae-250.0.0; _csrf=xm7Y1cV8kQ3gJ1MAE7jO84Vt'
}

pd = requests.get(args.url, headers=headers)
parse = BeautifulSoup(pd.text, "html.parser")
title = parse.find("title").string.replace(" - Novel Live - Reading Novel Free", "")
nextUrl = args.url

Finished = object()



def writeToEpub(writeQueue, path):
    logger.debug(f"writeToEpub(queue, {path})")
    book = epub.EpubBook()
    book.spine.append("nav")
    try:
        book.add_author(parse.find("span", {"property": "name"}).text.strip())
    except:
        pass
    toc = []
    # define CSS style
    style = "img {width: 70rem; display: block; max-width: 100%; margin: auto;}"
    nav_css = epub.EpubItem(
        uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style
    )

    # add CSS file
    book.add_item(nav_css)
    try:
        while True:
            task = writeQueue.get()
            if task == Finished:
                writeQueue.task_done()
                return
            try:
                result = task.result()
                toc.append(result)
                book.add_item(result)
                book.spine.append(result)
            except Exception as err:
                logger.error(err)
            writeQueue.task_done()
    finally:
        # add navigation files
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.toc = toc

        # write to the file
        epub.write_epub(f"{title}.epub", book, {})

def downloadChapter(url, num):
    for _ in range(5):
        try:
            with tempfile.TemporaryFile(mode="w+") as content:
                with requests.get(
                    url, headers=headers
                ) as pageDump:
                    logger.info(f"Downloading {url}")
                    parse = BeautifulSoup(pageDump.text, "html.parser")
                    text = parse.find('div', {'class': 'txt'})
                    chTitle = f'Chapter {num} - ' + re.sub(' - Novel Live.*', '', re.sub('^.*Chapter [0-9]+ ', '', parse.find('title').text))
                    
                    content.write(f"<h1>{chTitle}</h1>")
                    # remove any headers with the 'Chapter #' format
                    for chHeader in text.find_all(re.compile('^h'), text=re.compile('.*Chapter [0-9]*.*')):
                        chHeader.clear()
                    for p in text.find_all("p", recursive=False):
                        # Don't output anything that looks like the title - it was already printed
                        content.write(str(p))
                c = epub.EpubHtml(title=chTitle, file_name=f"page{num:04d}.html")
                logger.info(f"Writing {c.file_name}")
                content.seek(0)
                c.content = content.read()
                return c
        except Exception as err:
            logger.error(f"downloadChapter: {err}")
            time.sleep(2)


writeQueue = queue.Queue(maxsize=8)
threading.Thread(target=writeToEpub, args=(writeQueue, f"{title}.epub")).start()
idx = 1
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
    try:
        while True:
            for url in [
                    a.get("href")
                    for a in parse.find('div', {'class': 'm-newest2'}).find('ul', {'class':"ul-list5"}).find_all('a')
                ]:
                if idx >= args.start:
                    writeQueue.put(executor.submit(downloadChapter, urljoin(nextUrl, url), idx))
                idx += 1
                if idx > args.end and args.end != -1:
                    break
            if idx > args.end and args.end != -1:
                    break
            nextLink = parse.find('a', string="Next")
            if not nextLink:
                break
            nextUrl = urljoin(
                args.url, parse.find('a', string="Next").get('href')
            )
            pd = requests.get(nextUrl, headers=headers)
            parse = BeautifulSoup(pd.text, "html.parser")
            
    finally:
        writeQueue.put(Finished)
        