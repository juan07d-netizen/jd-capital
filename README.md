# JD Capital 2.1

JD Capital is a local-first personal wealth-building research system. It is intentionally **not** a custodial wallet and it never performs automatic spending or investment transactions.

## V1 acceptance target

`install → create user → login → record money → record opportunity → run live web research → save result → close → reopen → confirm persistence`

## Architecture

- FastAPI local web application bound to `127.0.0.1` only.
- SQLite in the per-user application data directory by default.
- Optional PostgreSQL path retained for a future hosted deployment.
- Password hashes use Argon2id.
- OpenAI API credentials use the operating system credential store when available; environment variables remain supported for development/test use.
- Long-running research is submitted with OpenAI Responses background mode. The provider response id is persisted before polling so a restart can resume a provider-backed job.
- Research uses the Responses API `web_search` tool and includes Argentina as an approximate search location.
- Automatic spending is disabled by design.

## Windows installation

`build_windows.ps1` creates a PyInstaller executable and then an Inno Setup installer when run on Windows with Python 3.13 x64 and Inno Setup 6 installed.

The repository also contains a GitHub Actions workflow that runs the complete test suite on Windows and creates `JD_Capital_Setup.exe` as an artifact for a tagged release or manual dispatch.

## Secrets

Do not put a production OpenAI API key in source control. In the desktop application, use the **Conexión IA** section to store/remove the key in the OS credential manager.

## Tests

Run:

```text
python -m pytest -q
```

The test suite covers persistence, idempotent migrations, legacy migration, HTTP login/API flow, the OpenAI background/web-search request contract, provider errors, and job recovery. It does not make a real paid API call.

A real research test remains a controlled acceptance test because it requires a valid OpenAI API key and incurs API usage.


## Build de Windows

La compilación final para Windows se realiza en un runner Windows de GitHub Actions. El workflow `.github/workflows/windows-installer.yml` ejecuta la suite de pruebas, construye el ejecutable con PyInstaller, genera el instalador con Inno Setup y publica el instalador junto con su SHA-256.

No se suben credenciales ni claves de OpenAI al repositorio. La clave se carga por primera vez dentro de JD Capital y se almacena en el almacén de credenciales del sistema operativo.
