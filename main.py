import csv
import os
import subprocess
from collections import Counter
from glob import glob
from time import sleep
import click

from dataclasses import dataclass
import yaml
import requests
from nltk import word_tokenize
from rich import print
from rich.progress import track
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
from bs4 import BeautifulSoup

from wiki_thresher.html_xform import apply_html_transformations
from wiki_thresher.mwtext_xform import apply_mwtext_transformations


@dataclass
class MWText:
    id: int
    rev_id: int
    text: str
    title: str
    file_safe_url: str
    url: str
    ns: str


@click.group()
def top():
    pass


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
        #print(f"Reading from cached value at {path}")
        with open(path, 'r') as f:
            return f.read()

    try:
        page = page_soup_to_object(config, page)
    except KeyError:
        print("Error while trying to get URL info for " + page.id.text)
        return None
    mwtext = apply_mwtext_transformations(config, page.text)

    html = parsoid_convert_via_cli(config, mwtext)
    html = apply_html_transformations(config, html, page)
    if out_dir is not None:
        with open(path, 'w') as f:
            f.write(str(html))
        print(f"Wrote to {path}")
    sleep(0.1)
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


@click.command()
@click.argument("dir", type=str)
def stat(dir):
    counter = Counter()
    for filepath in sorted(glob(f"{dir}/*.html")):
        with open(filepath, 'r') as f:
            soup = BeautifulSoup(f.read(), "html.parser")
            if soup is None:
                continue
        text_elt = soup.find("text")
        if text_elt is None:
            print(f"Error reading {filepath}")
        else:
            if text_elt["ns"] == "0":
                text = text_elt.text
                tokens = word_tokenize(text)
                for token in tokens:
                    counter[token] += 1
    print(sum(counter.values()))
    with open("vocab.tsv", 'wt') as f:
        writer = csv.writer(f, delimiter='\t')
        for k, v in sorted(counter.items(), key=lambda x:-x[1]):
            writer.writerow([k, v])


if __name__ == '__main__':
    top.add_command(process)
    top.add_command(stat)
    top()
