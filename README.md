# powershell-docset : A dash docset for powershell modules

`posh-to-dash.py` scrapes the newly announced `https://docs.microsoft.com/en-us/powershell/module/` website in order to create an offline dash-compatible archive to be viewed in `Dash`, `Zeal` or `Velocity` :


<p align="center">
<img alt="Powershell docset in Velocity" src="screenshots/posh-docset.PNG"/>
</p>

## Releases

* [v0.1 -- Minimal working version](https://github.com/lucasg/powershell-docset/releases/tag/v0.1)

## Create docset from sources

`posh-to-dash.py` relies on :

* `requests` for http(s) downloads
* `selenium` and `phantomjs` for webscraping
* `bs4` for html parsing and replacing

Start scraping by typing : `posh-to-dash.py --output $outputdir --version 6 --temporary`
	
* if `--output` is not provided, `posh-to-dash.py` use the working directory as output
* the `--version` switch support Powershell API versions `3.0`, `4.0`, `5.0`, `5.1` and `6` (default)
* `--temporary` specify to download the web scraping resources in a temporary folder instead of clobbering the current directory. However if the download fail, the results will be thrown out.

## Limitations

`posh-to-dash.py` is still written quick and dirty. It may or may not work on your machine.
Don't be mad if it don't work on your machine.

The powershell modules API endpoint is also quite new, so it may be subject to breakage by the `docs.microsoft.com` people.
