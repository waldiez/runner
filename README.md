# Waldiez Runner

Run your [Waldiez](https://github.com/waldiez/waldiez) flows in isolated environments and stream AG2 logs/input/output via Redis.

<!-- markdownlint-disable MD034 -->

<video
  src="https://github.com/user-attachments/assets/596ee25a-362e-4202-a4b0-894a4713e041"
  controls="controls" autoplay="autoplay" loop="loop"
  muted="muted" playsinline="playsinline" width="100%" height="100%">
</video>

## Overview

Waldiez Runner enables executing flows in isolated Python virtual environments or containers, with full I/O streaming via Redis and task management via FastAPI + Taskiq.

Backed by:

- [FastAPI](https://fastapi.tiangolo.com/) for the HTTP API
- [Taskiq](https://taskiq.readthedocs.io/) for async task queuing and scheduling
- [Redis](https://redis.io/) for messaging and log/input/output streaming
- [PostgreSQL](https://www.postgresql.org/) for task and client persistence
- [Waldiez](https://github.com/waldiez/waldiez) + [ag2](https://github.com/ag2ai/ag2) + [FastStream](https://github.com/ag2ai/faststream) for defining, executing, and streaming interactive flows in isolation

![overview](https://raw.githubusercontent.com/waldiez/runner/refs/heads/main/docs/overview.jpg)

## Contributors ✨

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://scholar.google.com/citations?user=JmW9DwkAAAAJ"><img src="https://avatars.githubusercontent.com/u/29335277?v=4?s=100" width="100px;" alt="Panagiotis Kasnesis"/><br /><sub><b>Panagiotis Kasnesis</b></sub></a><br /><a href="#projectManagement-ounospanas" title="Project Management">📆</a> <a href="#research-ounospanas" title="Research">🔬</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/lazToum"><img src="https://avatars.githubusercontent.com/u/4764837?v=4?s=100" width="100px;" alt="Lazaros Toumanidis"/><br /><sub><b>Lazaros Toumanidis</b></sub></a><br /><a href="https://github.com/waldiez/waldiez/commits?author=lazToum" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://humancentered.gr/"><img src="https://avatars.githubusercontent.com/u/3456066?v=4?s=100" width="100px;" alt="Stella Ioannidou"/><br /><sub><b>Stella Ioannidou</b></sub></a><br /><a href="#promotion-siioannidou" title="Promotion">📣</a> <a href="#design-siioannidou" title="Design">🎨</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/amaliacontiero"><img src="https://avatars.githubusercontent.com/u/29499343?v=4?s=100" width="100px;" alt="Amalia Contiero"/><br /><sub><b>Amalia Contiero</b></sub></a><br /><a href="https://github.com/waldiez/vscode/commits?author=amaliacontiero" title="Code">💻</a> <a href="https://github.com/waldiez/vscode/issues?q=author%3Aamaliacontiero" title="Bug reports">🐛</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/hchris0"><img src="https://avatars.githubusercontent.com/u/23460824?v=4?s=100" width="100px;" alt="Christos Chatzigeorgiou"/><br /><sub><b>Christos Chatzigeorgiou</b></sub></a><br /><a href="https://github.com/waldiez/runner/commits?author=hchris0" title="Code">💻</a></td>
    </tr>
  </tbody>
  <tfoot>
    <tr>
      <td align="center" size="13px" colspan="7">
        <img src="https://raw.githubusercontent.com/all-contributors/all-contributors-cli/1b8533af435da9854653492b1327a23a4dbd0a10/assets/logo-small.svg">
          <a href="https://all-contributors.js.org/docs/en/bot/usage">Add your contributions</a>
        </img>
      </td>
    </tr>
  </tfoot>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!

## License

This project is licensed under the [Apache License, Version 2.0 (Apache-2.0)](https://github.com/waldiez/vscode/blob/main/LICENSE).
