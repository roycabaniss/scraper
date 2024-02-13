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

pd = requests.get(args.url, headers={"User-Agent": "Mozilla/5.0"})
parse = BeautifulSoup(pd.text, "html.parser")
title = parse.find("title").string.replace("| Royal Road", "")

nextUrl = urljoin(
    args.url, parse.find("span", string="Start Reading").find_parent("a").get("href")
)
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


def fetchImage(url: str):
    for _ in range(5):
        try:
            with requests.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "referer": "https://readmanganato.com/",
                },
            ) as response:
                response.raise_for_status()
                with io.BytesIO(
                    response.content
                ) as image_bytes, io.BytesIO() as img_dst:
                    with Image.open(image_bytes) as img:
                        img.save(img_dst, format=img.format, quality=50, optimize=True)
                        return f"data:image/{img.format};base64,{base64.b64encode(img_dst.getvalue()).decode()}"
        except Exception as err:
            logger.error(f"fetchImage: {err}")


def downloadChapter(url, num):
    for _ in range(5):
        try:
            with tempfile.TemporaryFile(mode="w+") as content:
                with requests.get(
                    url, headers={"User-Agent": "Mozilla/5.0"}
                ) as pageDump:
                    logger.info(f"Downloading {url}")
                    parse = BeautifulSoup(pageDump.text, "html.parser")
                    chTitle = parse.find("div", {"class": "fic-header"}).find("h1").text

                    content.write(f"<h1>{chTitle}</h1>")
                    for chDiv in parse.find_all("div", {"class": "chapter-content"}):
                        for img in chDiv.find_all("img"):
                            img["src"] = fetchImage(urljoin(url, img.get("src")))
                        content.write(str(chDiv))
                c = epub.EpubHtml(title=chTitle, file_name=f"page{num:03d}.html")
                content.seek(0)
                c.content = content.read()
                return c
        except Exception as err:
            logger.error(f"downloadChapter: {err}")
            time.sleep(2)


writeQueue = queue.Queue(maxsize=1)
threading.Thread(target=writeToEpub, args=(writeQueue, f"{title}.epub")).start()
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
    for idx, url in enumerate(
        [
            x.a.get("href")
            for x in parse.find("table", {"id": "chapters"}).find_all("tr")[
                1 + args.start : args.end
            ]
        ],
        args.start,
    ):
        writeQueue.put(executor.submit(downloadChapter, urljoin(nextUrl, url), idx))
    writeQueue.put(Finished)
