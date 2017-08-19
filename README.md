# powershell-docset : A dash docset for powershell modules

`posh-to-dash.py` scrapes the newly announced `https://docs.microsoft.com/en-us/powershell/module/` website in order to create an offline dash-compatible archive to be viewed in `Dash`, `Zeal` or `Velocity` :


<p align="center">
<img alt="Powershell docset in Velocity" src="screenshots/posh-docset.PNG"/>
</p>

## Releases

* [v0.1 -- Minimal working version](https://github.com/lucasg/powershell-docset/releases/tag/v0.1)
* [v0.2 -- Offline mode supported](https://github.com/lucasg/powershell-docset/releases/tag/v0.2)
* [v0.3 -- travis setup](https://github.com/lucasg/powershell-docset/releases/tag/v0.3)
* [v0.4 -- user contributed docset](https://github.com/lucasg/powershell-docset/releases/tag/v0.4)

## Create docset from sources

`posh-to-dash.py` relies on :

* `requests` for http(s) downloads
* `selenium` and `phantomjs` for webscraping
* `bs4` for html parsing and rewriting

Start scraping by typing : `posh-to-dash.py --output=$outputfile --version=6 --temporary`
	
* if `--output` is not provided, `posh-to-dash.py` will output "Powershell.tgz' into the working directory
* the `--version` switch support Powershell API versions `3.0`, `4.0`, `5.0`, `5.1` and `6` (default)
* `--temporary` specify to download the web scraping resources in a temporary folder instead of clobbering the current directory. However if the download fail, the results will be thrown out.

## Limitations

The powershell modules API endpoint is quite new, so it may be subject to breakage by the `docs.microsoft.com` people.
