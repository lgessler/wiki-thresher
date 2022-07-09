
# Usage

Note: you will need PHP 7 available via command line--check `php -v`.

1. Decompress a Wikipedia `.bz2` (e.g. from `https://dumps.wikimedia.org/wowiki/latest/wowiki-latest-pages-articles.xml.bz2`) in `input/`

2. Examine existing configs in `configs/` and make one for your language.

3. Begin scraping by running `python main.py -c configs/your_config.yml input/your_dump.xml output/yourlang`

4. Filter out non-namespace 0 articles using `python main.py filter output/yourlang output/yourlang_filtered`

5. Use `python main.py stat output/yourlang_filtered` to look at a rough count of tokens.
