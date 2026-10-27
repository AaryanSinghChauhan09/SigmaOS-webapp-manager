    # SigmaOS-webapp-manager

    Turn websites into desktop webapps

    Part of the **SigmaOS** sovereign operating-system ecosystem — a multi-repository
    distribution modelled on Linux Mint and Omarchy Linux. See the parent
    [`SigmaOS`](https://github.com/AaryanSinghChauhan09/SigmaOS) repository for the
    full component index.

    ## Upstream inspirations
    - https://github.com/linuxmint/webapp-manager

    ## Design principles applied
    - **Defensive Programming**
- **Fail-Fast**
- **Separation of Concerns**
- **KISS**
- **Deterministic Testing**

    ## Usage
    Verbs: `create, list, remove, isolate-plan`

    ```
    $ sigma-webapp create "Mail" https://mail.example.com --write
~/.local/share/applications/mail.desktop
$ sigma-webapp list
Mail  https://mail.example.com  chromium
$ sigma-webapp remove ~/.local/share/applications/mail.desktop --apps-dir ~/.local/share/applications --execute
$ sigma-webapp isolate-plan https://mail.example.com
chromium --user-data-dir=... --app=https://mail.example.com

    ```

    ## Build & test
    ```
    make build
    make test
    ```

    ## Licence
    GNU General Public License v3.0 (FOSS).
