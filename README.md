# 🌐 QGIS Certification Website [![DPG Badge](https://img.shields.io/badge/Verified-DPG-3333AB?logo=data:image/svg%2bxml;base64,PHN2ZyB3aWR0aD0iMzEiIGhlaWdodD0iMzMiIHZpZXdCb3g9IjAgMCAzMSAzMyIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTE0LjIwMDggMjEuMzY3OEwxMC4xNzM2IDE4LjAxMjRMMTEuNTIxOSAxNi40MDAzTDEzLjk5MjggMTguNDU5TDE5LjYyNjkgMTIuMjExMUwyMS4xOTA5IDEzLjYxNkwxNC4yMDA4IDIxLjM2NzhaTTI0LjYyNDEgOS4zNTEyN0wyNC44MDcxIDMuMDcyOTdMMTguODgxIDUuMTg2NjJMMTUuMzMxNCAtMi4zMzA4MmUtMDVMMTEuNzgyMSA1LjE4NjYyTDUuODU2MDEgMy4wNzI5N0w2LjAzOTA2IDkuMzUxMjdMMCAxMS4xMTc3TDMuODQ1MjEgMTYuMDg5NUwwIDIxLjA2MTJMNi4wMzkwNiAyMi44Mjc3TDUuODU2MDEgMjkuMTA2TDExLjc4MjEgMjYuOTkyM0wxNS4zMzE0IDMyLjE3OUwxOC44ODEgMjYuOTkyM0wyNC44MDcxIDI5LjEwNkwyNC42MjQxIDIyLjgyNzdMMzAuNjYzMSAyMS4wNjEyTDI2LjgxNzYgMTYuMDg5NUwzMC42NjMxIDExLjExNzdMMjQuNjI0MSA5LjM1MTI3WiIgZmlsbD0id2hpdGUiLz4KPC9zdmc+Cg==)](https://blog.qgis.org/2025/02/08/qgis-recognized-as-digital-public-good/)

[![image](https://github.com/user-attachments/assets/88e08b1f-2dd1-4311-9ebf-9b3ef91b64dc)](https://certification.qgis.org)


> ## 👋 Welcome to the QGIS Certification Website!
>
> **This repository hosts the source code for the QGIS Certification Website:**
>
> 🌍 [https://certification.qgis.org](https://certification.qgis.org)
>
> Here you'll find everything you need to **build, develop, and contribute** to this site.
>
> ### ⚠️ Note on Other QGIS Websites
>
> **This repository is _only_ for the QGIS Certification Website ([certification.qgis.org](https://certification.qgis.org)).**
>
> If you are looking for the source code or want to contribute to other QGIS websites, please visit their respective repositories below.
> Each website has its own codebase and contribution process:
>
> - [qgis.org](https://qgis.org) ([GitHub: QGIS-Website](https://github.com/qgis/QGIS-Website)) – QGIS Main Wesite
> - [hub.qgis.org](https://hub.qgis.org) ([GitHub: QGIS-Hub-Website](https://github.com/qgis/QGIS-Hub-Website)) – QGIS Resources Hub
> - [plugins.qgis.org](https://plugins.qgis.org) ([GitHub: QGIS-Plugins-Website](https://github.com/qgis/QGIS-Plugins-Website)) – QGIS Plugins Repository
> - [planet.qgis.org](https://planet.qgis.org) ([GitHub: QGIS-Planet-Website](https://github.com/qgis/QGIS-Planet-Website)) – QGIS Planet Blog Aggregator
> - [changelog.qgis.org](https://changelog.qgis.org) ([GitHub: QGIS-Changelog-Website](https://github.com/qgis/QGIS-Changelog-Website)) – QGIS Changelog Editor
> - [members.qgis.org](https://members.qgis.org) ([GitHub: QGIS-Members-Website](https://github.com/qgis/QGIS-Members-Website)) – QGIS Sustaining Members Website
> - [feed.qgis.org](https://feed.qgis.org) ([GitHub: qgis-feed](https://github.com/qgis/qgis-feed)) – QGIS Feed Manager
> - [uc2025.qgis.org](https://uc.qgis.org) ([GitHub: QGIS-UC-Website](https://github.com/qgis/QGIS-UC-Website)) – QGIS User Conference Website
>

![-----------------------------------------------------](./img/green-gradient.png)


<!-- TABLE OF CONTENTS -->
<h2 id="table-of-contents"> 📖 Table of Contents</h2>

<details open="open">
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#-project-overview"> 🚀 Project Overview </a></li>
    <li><a href="#-qa-status"> 🚥 QA Status </a></li>
    <li><a href="#-license"> 📜 License </a></li>
    <li><a href="#-folder-structure"> 📂 Folder Structure </a></li>
    <li><a href="#️-data-model"> 🗄️ Data Model </a></li>
    <li><a href="#-using-the-nix-shell"> 🧊 Using the Nix Shell </a></li>
    <li><a href="#-contributing"> ✨ Contributing </a></li>
    <li><a href="#-have-questions"> 🙋 Have Questions? </a></li>
    <li><a href="#-contributors"> 🧑‍💻👩‍💻 Contributors </a></li>
    <li><a href="#-credits"> 🙏 Credits </a></li>
  </ol>
</details>

![-----------------------------------------------------](./img/green-gradient.png)

## 🚀 Project Overview

![Overview](./img/certification-qgis-org.gif)

![-----------------------------------------------------](./img/green-gradient.png)


## 🚥 QA Status

### 🪪 Badges
| Badge | Description |
|-------|-------------|
| [![Lint and Django Unit Tests](https://github.com/qgis/QGIS-Certification-Website/actions/workflows/test.yaml/badge.svg)](https://github.com/qgis/QGIS-Certification-Website/actions/workflows/test.yaml) | Lint and Django Unit Tests |
| [![Build and Push Docker Image to DockerHub](https://github.com/qgis/QGIS-Certification-Website/actions/workflows/build-push-images-release.yaml/badge.svg)](https://github.com/qgis/QGIS-Certification-Website/actions/workflows/build-push-images-release.yaml) | Build and Push Docker Image to DockerHub |
| ![Website Status](https://img.shields.io/website-up-down-green-red/https/certification.qgis.org.svg) | Website availability status |
| ![License](https://img.shields.io/github/license/qgis/QGIS-Certification-Website.svg) | Repository license |
| ![](https://img.shields.io/github/issues/qgis/QGIS-Certification-Website.svg) | Open issues count |
| ![](https://img.shields.io/github/issues-closed/qgis/QGIS-Certification-Website.svg) | Closed issues count |
| ![](https://img.shields.io/github/issues-pr/qgis/QGIS-Certification-Website.svg) | Open pull requests count |
| ![](https://img.shields.io/github/issues-pr-closed/qgis/QGIS-Certification-Website.svg) | Closed pull requests count |


### ⭐️ Project Stars

![Stars](https://starchart.cc/qgis/QGIS-Certification-Website.svg)

![-----------------------------------------------------](./img/green-gradient.png)


## 📜 License

This project is licensed under the GPLv3 License. See the [COPYING](./COPYING) file for details.

![-----------------------------------------------------](./img/green-gradient.png)


## 📂 Folder Structure

```plaintext
QGIS-Certification-Website/
├── 📦 deployment/                  # Deployment scripts and configuration
├── 🛰️ django_project/              # Main Django application source code
├── 🖼️ img/                         # Images and media assets for this README
├── 🧪 codecov.yml                  # Codecov configuration for test coverage
├── 📜 COPYING                      # Project license file (GPL-2.0)
├── 📝 list-vscode-extensions.sh*   # List recommended VSCode extensions for Nix shell
├── 👥 MAINTAINERS                  # Maintainers list
├── 📖 README.md                    # Project overview and documentation (this file)
├── 📦 REQUIREMENTS-dev.txt         # Python dependencies for development
├── 📦 REQUIREMENTS.txt             # Python dependencies for production
├── 🧊 shell.nix                    # Nix shell environment definition
└── 🖥️ vscode.sh*                   # VSCode helper script for Nix shell
```

![-----------------------------------------------------](./img/green-gradient.png)


## 🗄️ Data Model

TODO: Refactor the models and remove unused app

![-----------------------------------------------------](./img/green-gradient.png)

## 🧊 Using the Nix Shell

Please refer to the [Nix section](./CONTRIBUTING.md#️-nix) in [CONTRIBUTING.md](./CONTRIBUTING.md).

![-----------------------------------------------------](./img/green-gradient.png)

## ✨ Contributing

We welcome contributions! Please read the [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to get started.

![-----------------------------------------------------](./img/green-gradient.png)

## 🙋 Have Questions?

Have questions or feedback? Feel free to open an issue or submit a Pull Request!

![-----------------------------------------------------](./img/green-gradient.png)
## 🧑‍💻👩‍💻 Contributors

Thank you to the individual contributors who have helped to build the QGIS Sustaining Members Website:
- Tim Sutton (Lead developer): tim@kartoza.com
- Dražen Odobašić: dodobas@geoinfo.geof.hr
- George Irwin: github@grvhi.com
- Ismail Sunni: imajimatika@gmail.com
- Richard Duivenvoorde: richard@duif.net
- Rischan Mafrur: [@rischanlab](https://github.com/rischanlab)
- Etienne Trimaille: [@gustry](https://github.com/gustry)
- Anita Hapsari: [@ann26](https://github.com/ann26)
- Muhammad Yarjuna Rohmat: [@myarjunar](https://github.com/myarjunar)
- [Kontur Team](https://www.kontur.io) – Responsible for the design of the current theme
- Lova Andriarimalala: [@Xpirix](https://github.com/Xpirix)

![-----------------------------------------------------](./img/green-gradient.png)

## 🙏 Credits

The original project called [Projecta](https://github.com/kartoza/projecta.git) was funded and developed by [Kartoza.com](http://kartoza.com) and individual contributors.

![-----------------------------------------------------](./img/green-gradient.png)

Made with ❤️ by Tim Sutton (@timlinux), Lova Andriarimalala (@Xpirix) and QGIS Contributors.
