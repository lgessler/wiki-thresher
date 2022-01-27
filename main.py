import os
import subprocess
from time import sleep

import click
from dataclasses import dataclass
import yaml
import requests
from rich import print
from rich.progress import track

from wiki_thresher.html_xform import apply_html_transformations
from wiki_thresher.mwtext_xform import apply_mwtext_transformations
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
from bs4 import BeautifulSoup


@dataclass
class MWText:
    id: int
    rev_id: int
    text: str
    title: str
    file_safe_url: str
    url: str
    ns: str


def page_soup_to_object(config, soup):
    revision = soup.find("revision")
    title = soup.find("title").text
    apicall = f'{config["api_url"]}?action=query&prop=info&titles={title}&format=json&inprop=url'
    resp = requests.get(apicall).json()
    id = soup.id.text
    obj = MWText(
        id=id,
        rev_id=revision.id.text,
        title=title,
        text=soup.find("text").text,
        file_safe_url=f"{config['url'].replace('.', '_')}__{id}.html",
        url=resp["query"]["pages"][str(id)]["fullurl"],
        ns=soup.find("ns").text
    )
    return obj


def parsoid_convert_via_cli(config, mwtext):
    command = ["php", "parsoid/bin/parse.php", f"--domain={config['url']}", "--body_only=false"]
    if "api_url" in config:
        command.append(f"--apiURL={config['api_url']}")
    parser_subprocess = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    parser_subprocess.stdin.write(str(mwtext).encode("utf-8"))
    parser_subprocess.stdin.close()
    html = parser_subprocess.stdout.read().decode("utf-8")
    parser_subprocess.wait()
    return html


def process_page(config, page, out_dir=None):
    file_safe_url = f"{config['url'].replace('.', '_')}__{page.id.text}.html"
    path = f'{out_dir}/{file_safe_url}'
    if out_dir is not None and os.path.isfile(path):
        print(f"Reading from cached value at {path}")
        with open(path, 'r') as f:
            return f.read()

    try:
        page = page_soup_to_object(config, page)
    except KeyError:
        print("Error while trying to get URL info for " + page.id.text)
        with open(path, 'w') as f:
            f.write("")
        return ""
    mwtext = apply_mwtext_transformations(config, page.text)

    html = parsoid_convert_via_cli(config, mwtext)
    html = apply_html_transformations(config, html, page)
    if out_dir is not None:
        with open(path, 'w') as f:
            f.write(html.prettify())
        print(f"Wrote to {path}")
    sleep(0.2)
    return html


@click.command()
@click.argument("dump", type=click.File("r"))
@click.argument("out_dir", type=str)
@click.option("-c", "--config", type=click.File("r"))
def process(dump, out_dir, config):
    soup = BeautifulSoup(dump.read(), features="lxml")
    pages = soup.find_all("page")
    config = yaml.load(config.read(), Loader=Loader)
    os.makedirs(out_dir, exist_ok=True)

    for page in track(pages, "Scraping..."):
        process_page(config, page, out_dir)
    #list(pmap(lambda page: , pages))


if __name__ == '__main__':
    process()
