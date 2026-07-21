#!/usr/bin/env python3

import os
from jsmin import jsmin


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def min_name(filename):
    base, ext = os.path.splitext(filename)
    return base + '.min' + ext


def minify_js(filename):
    output = min_name(filename)

    with open(filename, 'r', encoding='utf-8') as f:
        source = f.read()

    with open(output, 'w', encoding='utf-8') as f:
        f.write(jsmin(source))

    print(f'JS  {filename}')
    print(f' -> {output}')


def minify_css(filename):
    output = min_name(filename)

    with open(filename, 'r', encoding='utf-8') as f:
        source = f.read()

    # Keep this conservative
    source = source.replace('\n', '')
    source = source.replace('\r', '')
    source = source.replace('\t', '')

    with open(output, 'w', encoding='utf-8') as f:
        f.write(source)

    print(f'CSS {filename}')
    print(f' -> {output}')


def process():

    # JavaScript modules
    js_folder = os.path.join(ROOT, 'jam', 'js', 'modules')

    for name in os.listdir(js_folder):
        if name.endswith('.js') and not name.endswith('.min.js'):
            minify_js(os.path.join(js_folder, name))


    # Core CSS files
    css_files = [
        os.path.join(ROOT, 'jam', 'css', 'jam.css'),
        os.path.join(ROOT, 'jam', 'css', 'jam12.css'),
        os.path.join(ROOT, 'jam', 'css', 'admin.css'),
    ]

    for filename in css_files:
        if os.path.exists(filename):
            minify_css(filename)


if __name__ == '__main__':
    process()
    print('Done.')
