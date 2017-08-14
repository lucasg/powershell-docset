#!/usr/bin/env python3

import sqlite3, os, urllib, subprocess, hashlib
import os
import re
import shutil
import logging
import json
import tarfile
import tempfile
import argparse
import urllib.parse
import urllib
import time

import requests
from bs4 import BeautifulSoup as bs, Tag # pip install bs4
from selenium import webdriver
from selenium.webdriver.common.keys import Keys  
from selenium.webdriver.chrome.options import Options


# CONFIGURATION
posh_doc_api_version = '0.2' # powershell doc api version, not this docset one.
posh_version = '6'
docset_name = 'Powershell'

domain = "docs.microsoft.com"
base_url = "%s/en-us/powershell/module" % domain
default_url = "https://%s/?view=powershell-%%s" % (base_url)
default_theme_uri = "_themes/docs.theme/master/en-us/_themes"
# default_toc = "https://docs.microsoft.com/api/apibrowser/powershell/modules?moniker=powershell-%s&api-version=%s"
default_toc = "https://%s/powershell-%%s/toc.json?view=powershell-%%s" % (base_url)

global_driver = None

def download_binary(url, output_filename):
    """ Download GET request as binary file """
    r = requests.get(url, stream=True)
    with open(output_filename, 'wb') as f:
        for data in r.iter_content(32*1024):
            f.write(data)

def download_textfile(url, output_filename):
    """ Download GET request as utf-8 text file """
    logging.debug("download_textfile : %s -> %s" % (url, output_filename))
    r = requests.get(url)
    with open(output_filename, 'w', encoding="utf8") as f:
        f.write(r.text)
    

def download_as_browser(url, output_filename):
    global global_driver
    #driver = webdriver.PhantomJS(executable_path="C:\\Users\\lucas\\AppData\\Roaming\\npm\\node_modules\\phantomjs-prebuilt\\lib\\phantom\\bin\phantomjs.exe")
    global_driver.get(url)

    #soupFromJokesCC = BeautifulSoup(driver.page_source) #page_source fetches page after rendering is complete
    with open(output_filename, 'w', encoding="utf8") as f:
        f.write(global_driver.page_source)

    #global_driver.save_screenshot(output_filename+'screen.png') # save a screenshot to disk
    


def download_and_fix_links(url, output_filepath, posh_version = posh_version, is_index =  False, documents_folder = None):
    """ Download and fix broken nav paths for modules index """
    global global_driver
    # r = requests.get(url)
    # index_html = r.text
    #driver = webdriver.PhantomJS(executable_path="C:\\Users\\lucas\\AppData\\Roaming\\npm\\node_modules\\phantomjs-prebuilt\\lib\\phantom\\bin\phantomjs.exe")
    try:
        global_driver.get(url)
        index_html = global_driver.page_source
    except (ConnectionResetError, urllib.error.URLError) as e:
        # we may have a triggered a anti-scraping time ban
        # Lay low for several seconds and get back to it.

        global_driver.quit()
        global_driver = webdriver.PhantomJS(executable_path="C:\\Users\\lucas\\AppData\\Roaming\\npm\\node_modules\\phantomjs-prebuilt\\lib\\phantom\\bin\phantomjs.exe")
        time.sleep(2)
        index_html = None

    # try a second time, and raise error if fail
    if not index_html:
        global_driver.get(url)
        index_html = global_driver.page_source


    soup = bs(index_html, 'html.parser')

    
    links = soup.findAll("a", { "data-linktype" : "relative-path"}) # for modules and cmdlet pages
    if is_index: # for index page
        content_table = soup.findAll("table", { "class" : "api-search-results standalone"})[0]
        links = content_table.findAll(lambda tag: tag.name == 'a' and 'ms.title' in tag.attrs)    # for index page   
                
    for link in links:
        # search replace <a href="(\w+-\w+)\?view=powershell-6" data-linktype="relative-path">
        #                <a href="$1.html" data-linktype="relative-path">
        if is_index:
            link_str_pattern = "([\w\.\/]+)\?view=powershell-%s" % posh_version
        else:
            link_str_pattern = "(\w+-\w+)\?view=powershell-%s" % posh_version

        link_pattern = re.compile(link_str_pattern)
        targets = link_pattern.findall(link['href'])
        if not len(targets): # badly formated 'a' link
            continue

        if is_index:
            uri_path = targets[0].lstrip('/').rstrip('/')
            fixed_link = soup.new_tag("a", href="%s/index.html" % (uri_path), **{ "ms.title" : link["ms.title"]})
        else:
            fixed_link = soup.new_tag("a", href="%s.html" % targets[0], **{ "data-linktype" : "relative-path"})

        print(link['href'], " -> ", fixed_link['href']) 
        fixed_link.string = link.string
        link.replaceWith(fixed_link)

    # remove unsupported nav elements
    nav_elements = [
        ["nav", { "class" : "doc-outline", "role" : "navigation"}],
        ["ul", { "class" : "breadcrumbs", "role" : "navigation"}],
        ["div", { "class" : "sidebar", "role" : "navigation"}],
        ["div", { "class" : "dropdown dropdown-full mobilenavi"}],
        ["p", { "class" : "api-browser-description"}],
        ["div", { "class" : "api-browser-search-field-container"}],
        ["div", { "class" : "pageActions"}],
        ["div", { "class" : "dropdown-container"}],
    ]

    for nav in nav_elements:
        nav_class, nav_attr = nav
        
        for nav_tag in soup.findAll(nav_class, nav_attr):
            _ = nav_tag.extract()

    # Fix themes uri paths
    soup = crawl_posh_themes(documents_folder, soup, output_filepath)

    # Export fixed html
    with open(output_filepath, 'wb') as o_index:

        fixed_html = soup.prettify("utf-8")
        o_index.write(fixed_html)

    #global_driver.save_screenshot(output_filepath+'screen.png') # save a screenshot to disk
    return index_html

        
def crawl_posh_themes(documents_folder, soup, current_filepath):
    
    theme_output_dir = os.path.join(documents_folder, domain)

    # downloading stylesheets
    for link in soup.findAll("link", { "rel" : "stylesheet"}):
        uri_path = link['href'].strip()

        if uri_path.lstrip('/').startswith(default_theme_uri):

            css_url = "https://%s/%s" % (domain, uri_path)
            css_filepath =  os.path.join(theme_output_dir, uri_path.lstrip('/'))

            os.makedirs(os.path.dirname(css_filepath), exist_ok = True)
            
            # do not download twice the same file
            if not os.path.exists(css_filepath):
                download_textfile(css_url, css_filepath)

                # fix source map css
                # $hex_encoded_id.$name.css -> $name.css
                css_filename = os.path.basename(uri_path)
                css_dirname  = os.path.dirname(css_filepath)

                r = re.compile("\w+\.([\w\.]+)")
                sourcemap_css_filename = r.match(css_filename).groups()[0]
                download_textfile(css_url, os.path.join(css_dirname, sourcemap_css_filename))

            # Converting to a relative link
            path = os.path.relpath(css_filepath, os.path.dirname(current_filepath))
            rel_uri = '/'.join(path.split(os.sep))
            link['href'] = rel_uri

    # downloading scripts
    for script in soup.findAll("script", {"src":True}):
        uri_path = script['src']

        if  uri_path.lstrip('/').startswith(default_theme_uri):

            script_url = "https://%s/%s" % (domain, uri_path)
            
            # path normalization : we can do better
            script_path = uri_path.lstrip('/')
            if -1 != script_path.find('?v='):
                script_path = script_path[0:script_path.find('?v=')]

            script_filepath =  os.path.join(theme_output_dir, script_path)
            os.makedirs(os.path.dirname(script_filepath), exist_ok = True)

            # do not download twice the same file
            if not os.path.exists(script_filepath):
                download_textfile(script_url, script_filepath)

            # Converting to a relative link
            path = os.path.relpath(script_filepath, current_filepath)
            rel_uri = '/'.join(path.split(os.sep))
            script['src'] = rel_uri
    
    return soup


def crawl_posh_documentation(documents_folder, posh_version = posh_version):
    """ Crawl and download Posh modules documentation """

    index = default_url % posh_version
    modules_toc = default_toc % (posh_version, posh_version)

    index_filepath = os.path.join(documents_folder, domain, "en-us", "index.html")
    download_and_fix_links(index, index_filepath, is_index= True, posh_version = posh_version, documents_folder = documents_folder)        

    modules_filepath = os.path.join(documents_folder, "modules.toc")
    download_textfile(modules_toc, modules_filepath)

    theme_output_dir = os.path.join(documents_folder, domain, default_theme_uri)
    os.makedirs(theme_output_dir, exist_ok = True)

    with open(modules_filepath, 'r') as modules_fd:
        modules = json.load(modules_fd)

        for module in modules['items'][0]['children']:

            module_url = urllib.parse.urljoin(modules_toc, module["href"])
            module_dir = os.path.join(documents_folder, base_url, module['toc_title'])

            os.makedirs(module_dir, exist_ok = True)
            module_filepath = os.path.join(module_dir, "index.html")

            logging.debug("downloading modules doc %s -> %s" %(module_url, module_filepath))
            mod_html = download_and_fix_links(module_url, module_filepath, posh_version = posh_version, documents_folder = documents_folder)

            for cmdlet in module['children']:
                cmdlet_name = cmdlet['toc_title']
                
                if cmdlet_name.lower() in ("about", "functions", "providers", "provider"): # skip special toc
                    continue
                
                logging.debug("cmdlet %s" % cmdlet)
                cmdlet_urlpath = cmdlet["href"]
                cmdlet_url = urllib.parse.urljoin(modules_toc, cmdlet_urlpath)
                cmdlet_filepath = os.path.join(module_dir, "%s.html" % cmdlet_name)

                logging.debug("downloading cmdlet doc %s -> %s" %(cmdlet_url, cmdlet_filepath))
                cmdlet_html = download_and_fix_links(cmdlet_url, cmdlet_filepath, posh_version = posh_version, documents_folder = documents_folder)
                

def insert_into_sqlite_db(cursor, name, record_type, path):
    """ Insert a new unique record in the sqlite database. """
    try:
        cursor.execute('SELECT rowid FROM searchIndex WHERE path = ?', (path,))
        dbpath = cursor.fetchone()
        cursor.execute('SELECT rowid FROM searchIndex WHERE name = ?', (name,))
        dbname = cursor.fetchone()

        if dbpath is None and dbname is None:
            cursor.execute('INSERT OR IGNORE INTO searchIndex(name, type, path) VALUES (?,?,?)', (name, record_type, path))
            logging.debug('DB add [%s] >> name: %s, path: %s' % (record_type, name, path))
        else:
            logging.debug('record exists')

    except:
        pass


def make_docset(source_dir, dst_dir, filename):
    """ 
    Tar-gz the build directory while conserving the relative folder tree paths. 
    Copied from : https://stackoverflow.com/a/17081026/1741450 
    """
    
    tar_filepath = os.path.join(dst_dir, '%s.tar' % filename)
    targz_filepath = os.path.join(dst_dir, '%s.tar.gz' % filename)
    docset_filepath = os.path.join(dst_dir, '%s.docset' % filename)

    with tarfile.open(tar_filepath, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))

    shutil.move(tar_filepath, targz_filepath)
    shutil.move(targz_filepath, docset_filepath) # can conflict with build dir name


def main(build_dir, dest_dir, args):
    global global_driver

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


    if not args.local:
        global_driver = webdriver.PhantomJS(executable_path="C:\\Users\\lucas\\AppData\\Roaming\\npm\\node_modules\\phantomjs-prebuilt\\lib\\phantom\\bin\phantomjs.exe")
    
        # Crawl and download powershell modules documentation
        crawl_posh_documentation(document_dir, posh_version = args.version)

        # Download icon for package
        download_binary("https://github.com/PowerShell/PowerShell/raw/master/assets/Powershell_16.png", os.path.join(docset_dir, "icon.png"))
        download_binary("https://github.com/PowerShell/PowerShell/raw/master/assets/Powershell_32.png", os.path.join(docset_dir, "icon@2x.png"))

        global_driver.quit()


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
        insert_into_sqlite_db(cur, module_name, "Module", "%s/%s/index.html" % (base_url, module_name))

        for f in filter(lambda x : os.path.isfile(os.path.join(module_dir, module_name, x)), os.listdir(module)):
            
            cmdlet_filename = os.path.basename(f)
            if cmdlet_filename == "index.html":
                continue

            cmdlet_name, html_ext = os.path.splitext(cmdlet_filename)
            insert_into_sqlite_db(cur, cmdlet_name, "Cmdlet", "%s/%s/%s" % (base_url, module_name, cmdlet_filename))
        

    # commit and close db
    db.commit()
    db.close()

    # output directory : $out/versions/$posh_version/Powershell.docset
    version_output_dir = os.path.join(dest_dir, "versions", "%s" % args.version)
    os.makedirs(version_output_dir, exist_ok=True)

    # tarball and gunzip the docset
    make_docset(
        docset_dir,
        version_output_dir,
        docset_name
    )

if __name__ == '__main__':

    

    parser = argparse.ArgumentParser(
        description='Dash docset creation script for Powershell modules and Cmdlets'
    )

    parser.add_argument("-vv", "--verbose", 
        help="increase output verbosity", 
        action="store_true"
    )

    parser.add_argument("-v", "--version", 
        help="select powershell API versions", 
        default = "6",
        choices = ["3.0", "4.0", "5.0", "5.1", "6"]
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
