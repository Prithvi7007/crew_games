# CREW Development Bridge artifact-sync staging package

This directory contains the conservative installer and eight offline tests. It is a staging package, NOT a production deployment.

## Validation

Run from this directory:

```bash
python3 -m unittest discover -v
python3 install_artifact_sync.py /tmp/crew-bridge-stage.Vk9ZQF
python3 install_artifact_sync.py /tmp/crew-bridge-stage.Vk9ZQF --apply
python3 -m py_compile /tmp/crew-bridge-stage.Vk9ZQF/bridge/core.py /tmp/crew-bridge-stage.Vk9ZQF/bridge/server.py /tmp/crew-bridge-stage.Vk9ZQF/runner/worker.py
```

The first installer call is a dry run; the --apply call changes ONLY the staging copy. The installer saves timestamped backups of original files. Inspect differences before considering activation. Never reset the live bridge checkout or touch /opt/crew. This installer does not add multi-repository support. Live Docker integration testing and activation remain separate.
