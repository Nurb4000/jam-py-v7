html_additional_pages = {
    'index': 'index.html',
    'showcase': 'showcase.html',
    'features': 'features.html',
}
templates_path = ['_templates']
source_suffix = ['.txt']
master_doc = 'contents'
project = u'Jam.py'
copyright = u'2022, Jam.py Team'
author = u'Andrew Yushev & Dean D. Babic'
language = "en"
exclude_patterns = [
    '_build',
    'requirements.txt'
]
pygments_style = 'sphinx'
todo_include_todos = False
html_favicon = '_static/favicon.ico'
html_static_path = ['_templates']
html_last_updated_fmt = '%b %d, %Y'
html_show_sourcelink = False
htmlhelp_basename = 'Jampydocumentationdoc'
latex_elements = {
}
latex_documents = [
  (master_doc, 'Jampydocumentation.tex', u'Jam.py Documentation',
   u'Andrew Yushev & Dean D. Babic', 'manual'),
]
man_pages = [
    (master_doc, 'jampydocumentation', u'Jam.py documentation Documentation',
     [author], 1)
]
texinfo_documents = [
  (master_doc, 'Jampydocumentation', u'Jam.py documentation Documentation',
   author, 'Jampydocumentation', 'One line description of project.',
   'Miscellaneous'),
]

