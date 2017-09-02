import os
import shutil
import argparse
from datetime import datetime

docset_json = """{
    "name": "Powershell",
    "version": "%s/%s",
    "archive": "Powershell.tgz",
    "author": {
        "name": "lucasg",
        "link": "https://github.com/lucasg"
    },
    "aliases": ["Windows shell",
                "posh",
                "Cmdlets",
                "Windows automation"],

    "specific_versions": [

        { 
            "version": "6",
            "archive": "versions/6/Powershell.tgz",
        },
        { 
            "version": "5.1",
            "archive": "versions/5.1/Powershell.tgz",
        },
        { 
            "version": "5.0",
            "archive": "versions/5.0/Powershell.tgz",
        },
        { 
            "version": "4.0",
            "archive": "versions/4.0/Powershell.tgz",
        },
        { 
            "version": "3.0",
            "archive": "versions/3.0/Powershell.tgz",
        },
    ]
}
"""

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Create a timestamped versionned docset.json file'
    )

    parser.add_argument("-v", "--version", 
        help="set powershell docset version",
        required=True
    )

    parser.add_argument("-o", "--output", 
        help="set output filepath", 
        default = os.path.join(os.getcwd(), "Powershell", "docset.json"),
    )

    args = parser.parse_args()

    with open(args.output, "w") as out:
        date = datetime.strftime(datetime.utcnow(), "%y-%m-%d")
        version = args.version.lstrip("v")
        out.write(docset_json % (version, date))