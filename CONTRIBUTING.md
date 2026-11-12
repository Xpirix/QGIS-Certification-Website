# ✨ Contributing to QGIS-Certficiation-Website

Thank you for your interest in contributing to the QGIS Certficiation Website! We welcome all types of contributions, including bug reports, feature suggestions, code improvements, and documentation updates. Please review the guidelines below to help ensure a smooth and effective contribution process.

## Contributions guidelines

### Reporting issues

- We do not accept text in issues/comments that are LLM (AI) generated as part of our policy (please see the [Using AI](#-using-ai-large-language-models) section for more details).
- **This repository is only for the QGIS Certification website (certification.qgis.org)** and we would appreciate if you could only report issues that are related to this website here.
Any issue related to other websites (e.g qgis.org, plugins.qgis.org) or the QGIS Desktop should be reported to their respective repository.
- If you are considering to submit a PR directly, **we recommend opening an issue first** explaining the bug or the request. That way, it can be discussed before you spend the effort addressing it.
- We recommend reporting each issue under its respective category. When pressing the **New issue** button, please choose one of `Bug Report`, `Development`, `Feature Request` category. Never use the `Blank issue` for any issue that is under these existing categories.
- We also recommend attaching any relevant details like screenshots, error logs, wireframe... that could help us have more context about the issue.
- When submitting an issue, you should be always responsive to any questions and concerns. If we do not get a timely response, we reserve the right to close the issue so that we can keep the list of in-play issues we have to deal with small.

### Submitting a pull request

When submitting a PR, we are expecting you take into consideration the following guidelines:

- We do not accept text in PR title/descriptions/comments that are LLM (AI) generated as part of our policy (please see the [Using AI](#-using-ai-large-language-models) section for more details).
- The PR should always include an open issue reference (e.g Fixes #1234) unless the changes have been already discussed and the full context is provided.
- Make small, atomic changes. Your changeset size should not exceed more than 300 lines of code.
- Any content, UI/UX changes must always have screenshots attached (desktop/mobile version). Screenshots are also very welcome on any other changes whenever possible.
- When submitting PR, you should be always responsive to any questions, comments and changes requests. As with open issues, we reserve the right to close PR's if we do not get needed feedback in a timely manner. We do this to keep the number of in-consideration PR's short and manageable.

### 🤖 Using 'AI' (Large Language Models)

If you follow the QGIS discussion lists, QEP's etc. you will see that the use of LLM's and QGIS' acceptance of this is still under discussion. We are not the LLM police and do not have any systematic way to check if you are using an LLM or not - we expect you to self declare your LLM usage in your PR comment. That said, we are not super enthusiastic about receiving LLM generated patches if we do not know and trust you, and suggest that if you are making your first contributions, do it the old fashioned way (using brains and brawn, not an LLM). If you are a regular contributor and we trust that that submissions you make are of a good quality, we will likely be more accepting of LLM based contributions.

**Code changes only:** As stated in our project policy in [QEP 408](https://github.com/qgis/QGIS-Enhancement-Proposals/blob/master/qep-408-ai-tool-policy.md), AI/LLM generated text content are not allowed in all QGIS GitHub repositories. This includes issues and PR titles, descriptions, comments... Only the source code changes is allowed to be generated with the help of AI/LLM.

![-----------------------------------------------------](./img/green-gradient.png)

## 🧑💻 Development Setup

To get started with development, you can run the application in debug mode using Docker Compose. Several helpful Docker Compose commands are already defined in the `deployment/Makefile`.

## 🏃 Prerequisites

This project requires [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) for both development and production environments. Please make sure both are installed on your system before proceeding.

![Docker logo](https://www.docker.com/wp-content/uploads/2022/03/Moby-logo.png)

Verify your installation with:
```bash
docker --version
docker-compose --version
```

![-----------------------------------------------------](./img/green-gradient.png)

## 🛒 Cloning the Repository

- Clone the repository:
  ```sh
  git clone https://github.com/qgis/QGIS-Certficiation-Website.git
  ```
- Check your current directory:
  ```sh
  pwd
  ```
- The repository path should be `<your current directory>/QGIS-Certficiation-Website`
- Navigate to the project directory:
  ```sh
  cd QGIS-Certficiation-Website/
  ```

![-----------------------------------------------------](./img/green-gradient.png)

## Pre-commit Hooks

This repository uses [pre-commit](https://pre-commit.com/) to automate code quality checks before each commit. To set it up:

1. Install pre-commit (if not already installed):
    ```sh
    pip install pre-commit
    ```

2. Install the hooks defined in `.pre-commit-config.yaml`:
    ```sh
    pre-commit install
    ```

Now, the configured checks (such as linting and formatting) will run automatically when you commit changes.

![-----------------------------------------------------](./img/green-gradient.png)

### ❄️ Nix

If you use Nix or NixOS, you can set up the development environment with:

```sh
nix-shell
./vscode.sh
```
*Note: The Nix shell will soon install all dependencies automatically.*

![-----------------------------------------------------](./img/green-gradient.png)

### ⚡️ Quick Start

- Generate your `.env` file from the example and update it with your email configuration:
  ```sh
  cd deployment
  cp .env.example .env
  nano .env  # Edit as needed
  ```

- Build and start the application:
  ```sh
  make build
  make devweb
  ```

- Run migrations and load initial data:
  ```sh
  make shell c=devweb
  python manage.py migrate
  python manage.py loaddata certification/fixtures/initial_data.json
  # Exit the shell with Ctrl+D
  ```

- Start the development server:
  ```sh
  make devweb-runserver
  ```

Open your browser and visit [http://localhost:62202](http://localhost:62202). The default super admin credentials are `qgisadmin` / `qgisadmin`.

![-----------------------------------------------------](./img/green-gradient.png)

### More Information

For detailed instructions, please refer to the [README-dev](./README-dev.md) and [README-docker](./README-docker.md) files. These documents provide comprehensive information about both development and production environments, similar to the original [Projecta](https://github.com/kartoza/projecta.git) application.

![-----------------------------------------------------](./img/green-gradient.png)
