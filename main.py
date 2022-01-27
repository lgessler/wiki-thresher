import subprocess

import click
from dataclasses import dataclass
import yaml
import requests

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
        url=resp["query"]["pages"][str(id)]["fullurl"]
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


def process_page(config, page):
    page = page_soup_to_object(config, page)
    mwtext = apply_mwtext_transformations(config, page.text)

    html = parsoid_convert_via_cli(config, mwtext)
    html = apply_html_transformations(config, html, page)
    with open('tmp.html', 'w') as f:
        f.write(html)
    return html

@click.command()
@click.argument("dump", type=click.File("r"))
@click.option("-c", "--config", type=click.File("r"))
def process(dump, config):
    soup = BeautifulSoup(dump.read(), features="lxml")
    pages = soup.find_all("page")
    config = yaml.load(config.read(), Loader=Loader)
    for page in pages:
        html = process_page(config, page)
        assert False


if __name__ == '__main__':
    process()
