#!/usr/bin/env python3

import sqlite3, os, urllib, subprocess, hashlib
import os
import shutil
import logging
import json
import tarfile
import tempfile
import argparse
import urllib.parse

from bs4 import BeautifulSoup as bs # pip install bs4
import requests


# CONFIGURATION
posh_doc_api_version = '0.2' # powershell doc api version, not this docset one.
posh_version = '6'
docset_name = 'Powershell'

base_url = "docs.microsoft.com/en-us/powershell/module"
default_url = "https://%s/?view=powershell-%%s" % (base_url)
# default_toc = "https://docs.microsoft.com/api/apibrowser/powershell/modules?moniker=powershell-%s&api-version=%s"
default_toc = "https://%s/powershell-%%s/toc.json?view=powershell-%%s" % (base_url)

def download_binary(url, output_filename):

    r = requests.get(url, stream=True)
    with open(output_filename, 'wb') as f:
        for data in r.iter_content(32*1024):
            f.write(data)

def download_textfile(url, output_filename):

    r = requests.get(url)
    with open(output_filename, 'w', encoding="utf8") as f:
        f.write(r.text)

def crawl_posh_documentation(documents_folder, posh_version = posh_version):

    index = default_url % posh_version
    modules_toc = default_toc % (posh_version, posh_version)

    index_filepath = os.path.join(documents_folder, "%s/index.html" % base_url)
    download_textfile(index, index_filepath)

    modules_filepath = os.path.join(documents_folder, "modules.toc")
    download_textfile(modules_toc, modules_filepath)

    with open(modules_filepath, 'r') as modules_fd:
        modules = json.load(modules_fd)

        for module in modules['items'][0]['children']:
            module_url = urllib.parse.urljoin(modules_toc, module["href"])

            module_dir = os.path.join(documents_folder, base_url, module['toc_title'])
            os.makedirs(module_dir, exist_ok = True)

            r = requests.get(module_url)
            module_filepath = os.path.join(module_dir, "index.html")
            download_textfile(module_url, module_filepath)
            

            for cmdlet in module['children']:
                cmdlet_name = cmdlet['toc_title']
                
                if cmdlet_name == "About" or cmdlet_name == "Providers": # skip special toc
                    continue

                cmdlet_urlpath = cmdlet["href"]
                cmdlet_url = urllib.parse.urljoin(modules_toc, cmdlet_urlpath)

                cmdlet_filepath = os.path.join(module_dir, "%s.html" % cmdlet_name)
                download_textfile(cmdlet_url, cmdlet_filepath)
            



def update_db(db, cur, name, typ, path):
    try:
        cur.execute('SELECT rowid FROM searchIndex WHERE path = ?', (path,))
        dbpath = cur.fetchone()
        cur.execute('SELECT rowid FROM searchIndex WHERE name = ?', (name,))
        dbname = cur.fetchone()

        if dbpath is None and dbname is None:
            cur.execute('INSERT OR IGNORE INTO searchIndex(name, type, path) VALUES (?,?,?)', (name, typ, path))
            logging.debug('DB add [%s] >> name: %s, path: %s' % (typ, name, path))
        else:
            logging.debug('record exists')

    except:
        pass


def make_docset(source_dir, dst_dir, filename):
    """ https://stackoverflow.com/a/17081026/1741450 """
    
    tar_filepath = os.path.join(dst_dir, '%s.tar' % filename)
    targz_filepath = os.path.join(dst_dir, '%s.tar.gz' % filename)
    docset_filepath = os.path.join(dst_dir, '%s.docset' % filename)

    with tarfile.open(tar_filepath, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))

    shutil.move(tar_filepath, targz_filepath)
    shutil.copy(targz_filepath, docset_filepath)


def main(build_dir, dest_dir, args):

    # Docset archive format
    """ 
        $root/
            $docset_name.docset/
                Contents/
                    Info.plist
                    Resources/
                        LICENSE
                        docSet.dsidx
                        Documents/
                            *
    """
    docset_dir = os.path.join(build_dir, "%s.docset" % docset_name)
    content_dir = os.path.join(docset_dir , "Contents")
    resources_dir = os.path.join(content_dir, "Resources")
    document_dir = os.path.join(resources_dir, "Documents")

    os.makedirs(document_dir, exist_ok=True)
    os.makedirs(os.path.join(document_dir, base_url), exist_ok=True)

    shutil.copy("Info.plist", content_dir)
    shutil.copy("LICENSE", resources_dir)


    # Crawl and download powershell modules documentation
    crawl_posh_documentation(document_dir)

    # Download icon for package
    download_binary("https://github.com/PowerShell/PowerShell/raw/master/assets/Powershell_16.png", os.path.join(docset_dir, "icon.png"))
    download_binary("https://github.com/PowerShell/PowerShell/raw/master/assets/Powershell_32.png", os.path.join(docset_dir, "icon@2x.png"))

    # Create database and index html doc
    sqlite_filepath = os.path.join(resources_dir, "docSet.dsidx")
    if os.path.exists(sqlite_filepath):
        os.remove(sqlite_filepath)

    db = sqlite3.connect(sqlite_filepath)
    cur = db.cursor()
    cur.execute('CREATE TABLE searchIndex(id INTEGER PRIMARY KEY, name TEXT, type TEXT, path TEXT);')
    cur.execute('CREATE UNIQUE INDEX anchor ON searchIndex (name, type, path);')

    module_dir = os.path.join(document_dir, base_url)
    modules = filter(lambda x : os.path.isdir(x), map(lambda y: os.path.join(module_dir, y), os.listdir(module_dir)))
    for module in modules:

        module_name = os.path.basename(module)
        # search replace <a href="(\w+-\w+)\?view=powershell-6" data-linktype="relative-path"> by <a href="$1.html" data-linktype="relative-path">

        update_db(db, cur, module_name, "Module", "%s/%s/index.html" % (base_url, module_name))

        for f in filter(lambda x : os.path.isfile(os.path.join(module_dir, module_name, x)), os.listdir(module)):
            
            cmdlet_filename = os.path.basename(f)
            if cmdlet_filename == "index.html":
                continue

            cmdlet_name, html_ext = os.path.splitext(cmdlet_filename)
            update_db(db, cur, cmdlet_name, "Cmdlet", "%s/%s/%s" % (base_url, module_name, cmdlet_filename))
        

    # commit and close db
    db.commit()
    db.close()

    # tarball and gunzip the docset
    make_docset(
        docset_dir,
        dest_dir,
        docset_name
    )

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Dash docset creation script for Powershell modules and Cmdlets'
    )

    parser.add_argument("-v", "--verbose", 
        help="increase output verbosity", 
        action="store_true"
    )

    parser.add_argument("-t", "--temporary", 
        help="Use a temporary directory for creating docset, otherwise use current dir.", 
        default=False, 
        action="store_true"
    )

    parser.add_argument("-l", "--local", 
        help="Do not download content. Only for development use.\n" + 
             "Incompatible with --temporary option", 
        default=False, 
        action="store_true"
    )

    parser.add_argument("-o", "--output", 
        help="set output directory", 
        default = os.getcwd(),
    )

    args = parser.parse_args()
    destination_dir = args.output

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)


    if args.temporary:
        with tempfile.TemporaryDirectory() as tmpdirname:
            main(tmpdirname, destination_dir, args)
    else:
        main(destination_dir, destination_dir, args)
    